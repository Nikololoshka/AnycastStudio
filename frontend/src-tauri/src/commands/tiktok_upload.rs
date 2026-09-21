use super::filesystem::{file_size, read_chunk};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::ipc::Channel;
use tauri::State;

const INIT_ENDPOINT: &str = "https://open.tiktokapis.com/v2/post/publish/video/init/";
const PREFERRED_CHUNK_SIZE: u64 = 10 * 1024 * 1024;
const MAX_ATTEMPTS: u32 = 5;
const BASE_BACKOFF_MS: u64 = 1000;
const MAX_BACKOFF_MS: u64 = 30_000;

#[derive(Default)]
pub struct TikTokUploadCancellations(Mutex<HashMap<String, Arc<AtomicBool>>>);

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PostInfo {
    pub title: String,
    pub privacy_level: String,
    pub disable_duet: bool,
    pub disable_comment: bool,
    pub disable_stitch: bool,
    pub is_aigc: bool,
    pub brand_organic_toggle: bool,
    #[serde(default)]
    pub video_cover_timestamp_ms: Option<u64>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UploadVideoParams {
    pub upload_id: String,
    pub path: String,
    pub mime_type: String,
    pub access_token: String,
    pub post_info: PostInfo,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UploadOutcome {
    pub publish_id: String,
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
                        "TikTok rejected the request with status {}: {}",
                        status.as_u16(),
                        body
                    ),
                })
            } else {
                Outcome::Fatal(UploadError::Fatal {
                    message: format!(
                        "TikTok upload failed with status {}: {}",
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
                    "TikTok request failed fatally: {}",
                    crate::logging::describe_error(&error)
                );
                return Err(error);
            }
            Outcome::Retry(reason) => {
                log::warn!(
                    "TikTok request attempt {} of {} failed: {}",
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
        "TikTok request gave up after {} attempts: {}",
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

fn compute_chunk_plan(total_size: u64) -> (u64, u32) {
    // chunk_size must never exceed total_size (TikTok rejects that as invalid),
    // so anything at or under the preferred chunk size uploads as a single chunk.
    let chunk_size = total_size.min(PREFERRED_CHUNK_SIZE).max(1);
    // TikTok wants floor division here: total_chunk_count = floor(video_size / chunk_size),
    // with the final chunk absorbing whatever remainder is left (it may exceed chunk_size,
    // up to 128MB) rather than the remainder becoming its own undersized trailing chunk.
    let total_chunk_count = (total_size / chunk_size).max(1) as u32;
    (chunk_size, total_chunk_count)
}

async fn initiate_upload(
    client: &reqwest::Client,
    access_token: &str,
    total_size: u64,
    chunk_size: u64,
    total_chunk_count: u32,
    post_info: &PostInfo,
) -> Result<(String, String), UploadError> {
    let body = serde_json::json!({
        "post_info": {
            "title": post_info.title,
            "privacy_level": post_info.privacy_level,
            "disable_duet": post_info.disable_duet,
            "disable_comment": post_info.disable_comment,
            "disable_stitch": post_info.disable_stitch,
            "is_aigc": post_info.is_aigc,
            "brand_organic_toggle": post_info.brand_organic_toggle,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": total_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunk_count,
        },
    });

    let mut body = body;
    if let Some(timestamp) = post_info.video_cover_timestamp_ms {
        body["post_info"]["video_cover_timestamp_ms"] = timestamp.into();
    }

    let response = with_retry(|| client.post(INIT_ENDPOINT).bearer_auth(access_token).json(&body).send())
        .await?;

    let body: serde_json::Value = response.json().await.map_err(|error| UploadError::Network {
        message: error.to_string(),
    })?;

    let publish_id = body
        .get("data")
        .and_then(|data| data.get("publish_id"))
        .and_then(|value| value.as_str())
        .ok_or_else(|| UploadError::Fatal {
            message: "TikTok init response did not include a publish_id".to_string(),
        })?
        .to_string();
    let upload_url = body
        .get("data")
        .and_then(|data| data.get("upload_url"))
        .and_then(|value| value.as_str())
        .ok_or_else(|| UploadError::Fatal {
            message: "TikTok init response did not include an upload_url".to_string(),
        })?
        .to_string();

    Ok((publish_id, upload_url))
}

async fn put_chunk(
    client: &reqwest::Client,
    upload_url: &str,
    mime_type: &str,
    chunk: Vec<u8>,
    offset: u64,
    total_size: u64,
) -> Result<reqwest::Response, UploadError> {
    with_retry(|| {
        let chunk = chunk.clone();
        client
            .put(upload_url)
            .header("Content-Type", mime_type)
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

fn cancellation_flag(state: &State<TikTokUploadCancellations>, upload_id: &str) -> Arc<AtomicBool> {
    let mut registry = state.0.lock().expect("upload cancellation lock poisoned");
    registry
        .entry(upload_id.to_string())
        .or_insert_with(|| Arc::new(AtomicBool::new(false)))
        .clone()
}

fn clear_cancellation(state: &State<TikTokUploadCancellations>, upload_id: &str) {
    state.0.lock().expect("upload cancellation lock poisoned").remove(upload_id);
}

#[tauri::command]
pub fn cancel_tiktok_upload(upload_id: String, state: State<TikTokUploadCancellations>) {
    log::info!("cancelling TikTok upload {upload_id}");
    if let Some(flag) = state.0.lock().expect("upload cancellation lock poisoned").get(&upload_id) {
        flag.store(true, Ordering::SeqCst);
    }
}

#[tauri::command]
pub async fn upload_video_tiktok(
    params: UploadVideoParams,
    state: State<'_, TikTokUploadCancellations>,
    on_progress: Channel<UploadProgressEvent>,
) -> Result<UploadOutcome, UploadError> {
    let cancelled = cancellation_flag(&state, &params.upload_id);

    log::info!(
        "TikTok upload {} starting for {} ({})",
        params.upload_id,
        params.path,
        params.mime_type
    );

    let result = run_upload(&params, &cancelled, &on_progress).await;
    clear_cancellation(&state, &params.upload_id);

    match &result {
        Ok(_) => log::info!("TikTok upload {} finished", params.upload_id),
        Err(error) => log::error!(
            "TikTok upload {} failed: {}",
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
    let (chunk_size, total_chunk_count) = compute_chunk_plan(total_size);

    let (publish_id, upload_url) = initiate_upload(
        &client,
        &params.access_token,
        total_size,
        chunk_size,
        total_chunk_count,
        &params.post_info,
    )
    .await?;

    let mut offset = 0u64;
    let mut last_status = 0u16;

    for chunk_index in 0..total_chunk_count {
        if cancelled.load(Ordering::SeqCst) {
            log::info!(
                "TikTok upload {} cancelled at offset {}",
                params.upload_id,
                offset
            );
            return Err(UploadError::Cancelled {
                message: "upload cancelled".to_string(),
            });
        }

        // The last chunk absorbs whatever remains, per TikTok's floor-division contract
        // in compute_chunk_plan — it may be larger than chunk_size (up to 128MB).
        let this_chunk_size = if chunk_index + 1 == total_chunk_count {
            total_size - offset
        } else {
            chunk_size
        };
        let chunk = read_chunk(&params.path, offset, this_chunk_size)
            .map_err(|message| UploadError::Fatal { message })?;

        let response =
            put_chunk(&client, &upload_url, &params.mime_type, chunk, offset, total_size).await?;
        last_status = response.status().as_u16();

        offset += this_chunk_size;

        log::debug!(
            "TikTok upload {} progressed to {} of {} bytes, chunk {} of {} returned status {}",
            params.upload_id,
            offset,
            total_size,
            chunk_index + 1,
            total_chunk_count,
            last_status
        );

        let _ = on_progress.send(UploadProgressEvent {
            uploaded_bytes: offset,
            total_bytes: total_size,
            percent: ((offset as f64 / total_size as f64) * 100.0).round() as u32,
        });
    }

    if last_status != 201 {
        return Err(UploadError::Fatal {
            message: format!(
                "TikTok did not confirm the completed upload: final chunk returned status {last_status}, expected 201"
            ),
        });
    }

    Ok(UploadOutcome { publish_id })
}
