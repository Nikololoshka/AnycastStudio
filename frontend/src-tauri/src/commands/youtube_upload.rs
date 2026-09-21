use super::filesystem::{file_size, read_chunk};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::ipc::Channel;
use tauri::State;

const UPLOAD_ENDPOINT: &str =
    "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status";
const CHUNK_SIZE: u64 = 1024 * 1024;
const MAX_ATTEMPTS: u32 = 5;
const BASE_BACKOFF_MS: u64 = 1000;
const MAX_BACKOFF_MS: u64 = 30_000;

#[derive(Default)]
pub struct UploadCancellations(Mutex<HashMap<String, Arc<AtomicBool>>>);

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VideoMetadata {
    pub title: String,
    pub description: String,
    pub tags: Vec<String>,
    pub privacy_status: String,
    pub category_id: String,
    pub license: String,
    pub embeddable: bool,
    pub public_stats_viewable: bool,
    pub made_for_kids: bool,
    pub contains_synthetic_media: bool,
    pub notify_subscribers: bool,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UploadVideoParams {
    pub upload_id: String,
    pub path: String,
    pub mime_type: String,
    pub access_token: String,
    pub metadata: VideoMetadata,
    pub session_uri: Option<String>,
    pub resume_offset: Option<u64>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UploadOutcome {
    pub video_id: String,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct UploadProgressEvent {
    pub uploaded_bytes: u64,
    pub total_bytes: u64,
    pub percent: u32,
}

#[derive(Debug, Serialize)]
struct ResumeState {
    session_uri: String,
    resume_offset: u64,
}

#[derive(Debug, Serialize)]
#[serde(tag = "type")]
pub enum UploadError {
    #[serde(rename = "network")]
    Network { message: String },
    #[serde(rename = "authentication")]
    Authentication { message: String, details: String },
    #[serde(rename = "platform")]
    Fatal { message: String, details: String },
    #[serde(rename = "unknown")]
    Cancelled { message: String },
}

enum Outcome {
    Response(reqwest::Response),
    Retry(String),
    Fatal(UploadError),
}

fn classify(result: Result<reqwest::Response, reqwest::Error>) -> Outcome {
    match result {
        Err(error) => Outcome::Retry(error.to_string()),
        Ok(response) => {
            let status = response.status();
            if status.is_success() || status.as_u16() == 308 {
                Outcome::Response(response)
            } else if status.as_u16() == 429 || status.is_server_error() {
                Outcome::Retry(format!("status {}", status.as_u16()))
            } else if status.as_u16() == 401 || status.as_u16() == 403 {
                Outcome::Fatal(UploadError::Authentication {
                    message: format!("YouTube rejected the request with status {}", status.as_u16()),
                    details: String::new(),
                })
            } else {
                Outcome::Fatal(UploadError::Fatal {
                    message: format!("YouTube upload failed with status {}", status.as_u16()),
                    details: String::new(),
                })
            }
        }
    }
}

fn jitter_ms(attempt: u32) -> u64 {
    let exponential = BASE_BACKOFF_MS.saturating_mul(1u64 << attempt.min(10)).min(MAX_BACKOFF_MS);
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.subsec_nanos() as u64)
        .unwrap_or(0);
    exponential / 2 + (nanos % (exponential / 2 + 1))
}

async fn with_retry<F, Fut>(mut send: F) -> Result<reqwest::Response, UploadError>
where
    F: FnMut() -> Fut,
    Fut: std::future::Future<Output = Result<reqwest::Response, reqwest::Error>>,
{
    let mut last_reason = String::new();
    for attempt in 0..MAX_ATTEMPTS {
        match classify(send().await) {
            Outcome::Response(response) => return Ok(response),
            Outcome::Fatal(error) => {
                log::error!(
                    "YouTube request failed fatally: {}",
                    crate::logging::describe_error(&error)
                );
                return Err(error);
            }
            Outcome::Retry(reason) => {
                log::warn!(
                    "YouTube request attempt {} of {} failed: {}",
                    attempt + 1,
                    MAX_ATTEMPTS,
                    reason
                );
                last_reason = reason;
                if attempt + 1 < MAX_ATTEMPTS {
                    tokio::time::sleep(Duration::from_millis(jitter_ms(attempt))).await;
                }
            }
        }
    }
    log::error!(
        "YouTube request gave up after {} attempts: {}",
        MAX_ATTEMPTS,
        last_reason
    );
    Err(UploadError::Network {
        message: format!(
            "upload failed after {} attempts: {}",
            MAX_ATTEMPTS, last_reason
        ),
    })
}

fn parse_confirmed_offset(range_header: Option<&str>) -> Option<u64> {
    let header = range_header?;
    let upper = header.strip_prefix("bytes=0-")?;
    upper.parse::<u64>().ok().map(|value| value + 1)
}

async fn initiate_session(
    client: &reqwest::Client,
    access_token: &str,
    mime_type: &str,
    total_size: u64,
    metadata: &VideoMetadata,
) -> Result<String, UploadError> {
    let body = serde_json::json!({
        "snippet": {
            "title": metadata.title,
            "description": metadata.description,
            "tags": metadata.tags,
            "categoryId": metadata.category_id,
        },
        "status": {
            "privacyStatus": metadata.privacy_status,
            "license": metadata.license,
            "embeddable": metadata.embeddable,
            "publicStatsViewable": metadata.public_stats_viewable,
            "selfDeclaredMadeForKids": metadata.made_for_kids,
            "containsSyntheticMedia": metadata.contains_synthetic_media,
        },
    });

    let endpoint = format!(
        "{UPLOAD_ENDPOINT}&notifySubscribers={}",
        metadata.notify_subscribers
    );

    let response = with_retry(|| {
        client
            .post(&endpoint)
            .bearer_auth(access_token)
            .header("X-Upload-Content-Type", mime_type)
            .header("X-Upload-Content-Length", total_size.to_string())
            .json(&body)
            .send()
    })
    .await?;

    response
        .headers()
        .get("Location")
        .and_then(|value| value.to_str().ok())
        .map(|value| value.to_string())
        .ok_or_else(|| UploadError::Fatal {
            message: "resumable session init returned no Location header".to_string(),
            details: String::new(),
        })
}

async fn put_chunk(
    client: &reqwest::Client,
    session_uri: &str,
    access_token: &str,
    chunk: Vec<u8>,
    offset: u64,
    total_size: u64,
) -> Result<reqwest::Response, UploadError> {
    with_retry(|| {
        let chunk = chunk.clone();
        client
            .put(session_uri)
            .bearer_auth(access_token)
            .header("Content-Length", chunk.len().to_string())
            .header(
                "Content-Range",
                format!(
                    "bytes {}-{}/{}",
                    offset,
                    offset + chunk.len() as u64 - 1,
                    total_size
                ),
            )
            .body(chunk)
            .send()
    })
    .await
}

fn cancellation_flag(state: &State<UploadCancellations>, upload_id: &str) -> Arc<AtomicBool> {
    let mut registry = state.0.lock().expect("upload cancellation lock poisoned");
    registry
        .entry(upload_id.to_string())
        .or_insert_with(|| Arc::new(AtomicBool::new(false)))
        .clone()
}

fn clear_cancellation(state: &State<UploadCancellations>, upload_id: &str) {
    state.0.lock().expect("upload cancellation lock poisoned").remove(upload_id);
}

#[tauri::command]
pub fn cancel_youtube_upload(upload_id: String, state: State<UploadCancellations>) {
    log::info!("cancelling YouTube upload {upload_id}");
    if let Some(flag) = state.0.lock().expect("upload cancellation lock poisoned").get(&upload_id) {
        flag.store(true, Ordering::SeqCst);
    }
}

#[tauri::command]
pub async fn upload_video_youtube(
    params: UploadVideoParams,
    state: State<'_, UploadCancellations>,
    on_progress: Channel<UploadProgressEvent>,
) -> Result<UploadOutcome, UploadError> {
    let cancelled = cancellation_flag(&state, &params.upload_id);

    log::info!(
        "YouTube upload {} starting for {} ({})",
        params.upload_id,
        params.path,
        params.mime_type
    );

    let result = run_upload(&params, &cancelled, &on_progress).await;
    clear_cancellation(&state, &params.upload_id);

    match &result {
        Ok(_) => log::info!("YouTube upload {} finished", params.upload_id),
        Err(error) => log::error!(
            "YouTube upload {} failed: {}",
            params.upload_id,
            crate::logging::describe_error(error)
        ),
    }

    result
}

async fn run_upload(
    params: &UploadVideoParams,
    cancelled: &Arc<AtomicBool>,
    on_progress: &Channel<UploadProgressEvent>,
) -> Result<UploadOutcome, UploadError> {
    let client = reqwest::Client::new();
    let total_size = file_size(&params.path).map_err(|message| UploadError::Fatal {
        message,
        details: String::new(),
    })?;

    log::info!(
        "YouTube upload {} covers {} bytes",
        params.upload_id,
        total_size
    );

    let session_uri = match &params.session_uri {
        Some(uri) => {
            log::info!(
                "YouTube upload {} resuming at offset {} on session {}",
                params.upload_id,
                params.resume_offset.unwrap_or(0),
                crate::logging::redact_url(uri)
            );
            uri.clone()
        }
        None => {
            initiate_session(
                &client,
                &params.access_token,
                &params.mime_type,
                total_size,
                &params.metadata,
            )
            .await?
        }
    };

    let mut offset = params.resume_offset.unwrap_or(0);

    while offset < total_size {
        if cancelled.load(Ordering::SeqCst) {
            log::info!(
                "YouTube upload {} cancelled at offset {}",
                params.upload_id,
                offset
            );
            return Err(UploadError::Cancelled {
                message: "upload cancelled".to_string(),
            });
        }

        let chunk_size = CHUNK_SIZE.min(total_size - offset);
        let chunk = read_chunk(&params.path, offset, chunk_size).map_err(|message| UploadError::Fatal {
            message,
            details: String::new(),
        })?;

        let response = match put_chunk(&client, &session_uri, &params.access_token, chunk, offset, total_size).await {
            Ok(response) => response,
            Err(UploadError::Authentication { message, .. }) => {
                let resume = ResumeState {
                    session_uri: session_uri.clone(),
                    resume_offset: offset,
                };
                return Err(UploadError::Authentication {
                    message,
                    details: serde_json::to_string(&resume).unwrap_or_default(),
                });
            }
            Err(error) => return Err(error),
        };

        let status = response.status().as_u16();
        if status == 200 || status == 201 {
            let body: serde_json::Value = response.json().await.map_err(|error| UploadError::Network {
                message: error.to_string(),
            })?;
            let video_id = body
                .get("id")
                .and_then(|value| value.as_str())
                .ok_or_else(|| UploadError::Fatal {
                    message: "YouTube response did not include a video id".to_string(),
                    details: String::new(),
                })?
                .to_string();

            let _ = on_progress.send(UploadProgressEvent {
                uploaded_bytes: total_size,
                total_bytes: total_size,
                percent: 100,
            });
            return Ok(UploadOutcome { video_id });
        }

        let range_header = response
            .headers()
            .get("Range")
            .and_then(|value| value.to_str().ok())
            .map(|value| value.to_string());
        offset = parse_confirmed_offset(range_header.as_deref()).unwrap_or(offset + chunk_size);

        log::debug!(
            "YouTube upload {} progressed to {} of {} bytes",
            params.upload_id,
            offset,
            total_size
        );

        let _ = on_progress.send(UploadProgressEvent {
            uploaded_bytes: offset,
            total_bytes: total_size,
            percent: ((offset as f64 / total_size as f64) * 100.0).round() as u32,
        });
    }

    Err(UploadError::Fatal {
        message: "resumable upload loop ended without a final response".to_string(),
        details: String::new(),
    })
}
