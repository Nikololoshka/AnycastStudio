use super::filesystem::{file_size, read_chunk};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::ipc::Channel;
use tauri::State;

const GRAPH_API_BASE: &str = "https://graph.facebook.com/v23.0";
const RUPLOAD_BASE: &str = "https://rupload.facebook.com/ig-api-upload/v23.0";
const CHUNK_SIZE: u64 = 4 * 1024 * 1024;
const MAX_ATTEMPTS: u32 = 5;
const BASE_BACKOFF_MS: u64 = 1000;
const MAX_BACKOFF_MS: u64 = 30_000;

#[derive(Default)]
pub struct InstagramUploadCancellations(Mutex<HashMap<String, Arc<AtomicBool>>>);

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MediaMetadata {
    pub caption: String,
    pub share_to_feed: bool,
    pub thumb_offset_ms: u64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UploadVideoParams {
    pub upload_id: String,
    pub path: String,
    pub mime_type: String,
    pub access_token: String,
    pub ig_user_id: String,
    pub metadata: MediaMetadata,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UploadOutcome {
    pub container_id: String,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct UploadProgressEvent {
    pub uploaded_bytes: u64,
    pub total_bytes: u64,
    pub percent: u32,
}

#[derive(Debug, Serialize)]
#[serde(tag = "type")]
pub enum UploadError {
    #[serde(rename = "network")]
    Network { message: String },
    #[serde(rename = "authentication")]
    Authentication { message: String },
    #[serde(rename = "platform")]
    Fatal { message: String },
    #[serde(rename = "unknown")]
    Cancelled { message: String },
}

enum Outcome {
    Response(reqwest::Response),
    Retry(String),
    Fatal(UploadError),
}

async fn classify(result: Result<reqwest::Response, reqwest::Error>) -> Outcome {
    match result {
        Err(error) => Outcome::Retry(error.to_string()),
        Ok(response) => {
            let status = response.status();
            if status.is_success() {
                return Outcome::Response(response);
            }
            let body = response.text().await.unwrap_or_default();
            if status.as_u16() == 429 || status.is_server_error() {
                Outcome::Retry(format!("status {}: {}", status.as_u16(), body))
            } else if status.as_u16() == 401 || status.as_u16() == 403 {
                Outcome::Fatal(UploadError::Authentication {
                    message: format!(
                        "Instagram rejected the request with status {}: {}",
                        status.as_u16(),
                        body
                    ),
                })
            } else {
                Outcome::Fatal(UploadError::Fatal {
                    message: format!(
                        "Instagram upload failed with status {}: {}",
                        status.as_u16(),
                        body
                    ),
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
        match classify(send().await).await {
            Outcome::Response(response) => return Ok(response),
            Outcome::Fatal(error) => {
                log::error!(
                    "Instagram request failed fatally: {}",
                    crate::logging::describe_error(&error)
                );
                return Err(error);
            }
            Outcome::Retry(reason) => {
                log::warn!(
                    "Instagram request attempt {} of {} failed: {}",
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
        "Instagram request gave up after {} attempts: {}",
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

async fn create_container(
    client: &reqwest::Client,
    access_token: &str,
    ig_user_id: &str,
    metadata: &MediaMetadata,
) -> Result<String, UploadError> {
    let thumb_offset = metadata.thumb_offset_ms.to_string();

    let response = with_retry(|| {
        client
            .post(format!("{GRAPH_API_BASE}/{ig_user_id}/media"))
            .query(&[
                ("media_type", "REELS"),
                ("upload_type", "resumable"),
                ("caption", metadata.caption.as_str()),
                ("share_to_feed", if metadata.share_to_feed { "true" } else { "false" }),
                ("thumb_offset", thumb_offset.as_str()),
                ("access_token", access_token),
            ])
            .send()
    })
    .await?;

    let body: serde_json::Value = response.json().await.map_err(|error| UploadError::Network {
        message: error.to_string(),
    })?;

    body.get("id")
        .and_then(|value| value.as_str())
        .map(|value| value.to_string())
        .ok_or_else(|| UploadError::Fatal {
            message: "Instagram container creation response did not include an id".to_string(),
        })
}

async fn put_chunk(
    client: &reqwest::Client,
    container_id: &str,
    access_token: &str,
    mime_type: &str,
    chunk: Vec<u8>,
    offset: u64,
    total_size: u64,
) -> Result<reqwest::Response, UploadError> {
    with_retry(|| {
        let chunk = chunk.clone();
        client
            .post(format!("{RUPLOAD_BASE}/{container_id}"))
            .header("Authorization", format!("OAuth {access_token}"))
            .header("offset", offset.to_string())
            .header("file_size", total_size.to_string())
            .header("Content-Type", mime_type)
            .body(chunk)
            .send()
    })
    .await
}

fn cancellation_flag(state: &State<InstagramUploadCancellations>, upload_id: &str) -> Arc<AtomicBool> {
    let mut registry = state.0.lock().expect("upload cancellation lock poisoned");
    registry
        .entry(upload_id.to_string())
        .or_insert_with(|| Arc::new(AtomicBool::new(false)))
        .clone()
}

fn clear_cancellation(state: &State<InstagramUploadCancellations>, upload_id: &str) {
    state.0.lock().expect("upload cancellation lock poisoned").remove(upload_id);
}

#[tauri::command]
pub fn cancel_instagram_upload(upload_id: String, state: State<InstagramUploadCancellations>) {
    log::info!("cancelling Instagram upload {upload_id}");
    if let Some(flag) = state.0.lock().expect("upload cancellation lock poisoned").get(&upload_id) {
        flag.store(true, Ordering::SeqCst);
    }
}

#[tauri::command]
pub async fn upload_video_instagram(
    params: UploadVideoParams,
    state: State<'_, InstagramUploadCancellations>,
    on_progress: Channel<UploadProgressEvent>,
) -> Result<UploadOutcome, UploadError> {
    let cancelled = cancellation_flag(&state, &params.upload_id);

    log::info!(
        "Instagram upload {} starting for {} ({})",
        params.upload_id,
        params.path,
        params.mime_type
    );

    let result = run_upload(&params, &cancelled, &on_progress).await;
    clear_cancellation(&state, &params.upload_id);

    match &result {
        Ok(_) => log::info!("Instagram upload {} finished", params.upload_id),
        Err(error) => log::error!(
            "Instagram upload {} failed: {}",
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
    let total_size = file_size(&params.path).map_err(|message| UploadError::Fatal { message })?;

    let container_id = create_container(&client, &params.access_token, &params.ig_user_id, &params.metadata).await?;

    let mut offset = 0u64;

    while offset < total_size {
        if cancelled.load(Ordering::SeqCst) {
            log::info!(
                "Instagram upload {} cancelled at offset {}",
                params.upload_id,
                offset
            );
            return Err(UploadError::Cancelled {
                message: "upload cancelled".to_string(),
            });
        }

        let this_chunk_size = CHUNK_SIZE.min(total_size - offset);
        let chunk = read_chunk(&params.path, offset, this_chunk_size)
            .map_err(|message| UploadError::Fatal { message })?;

        put_chunk(
            &client,
            &container_id,
            &params.access_token,
            &params.mime_type,
            chunk,
            offset,
            total_size,
        )
        .await?;

        offset += this_chunk_size;

        log::debug!(
            "Instagram upload {} progressed to {} of {} bytes",
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

    Ok(UploadOutcome { container_id })
}
