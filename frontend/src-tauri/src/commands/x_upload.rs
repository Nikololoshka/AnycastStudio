use super::filesystem::{file_size, read_chunk};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::ipc::Channel;
use tauri::State;

const UPLOAD_ENDPOINT: &str = "https://api.x.com/2/media/upload";
const PREFERRED_CHUNK_SIZE: u64 = 5 * 1024 * 1024;
const MAX_ATTEMPTS: u32 = 5;
const BASE_BACKOFF_MS: u64 = 1000;
const MAX_BACKOFF_MS: u64 = 30_000;

#[derive(Default)]
pub struct XUploadCancellations(Mutex<HashMap<String, Arc<AtomicBool>>>);

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UploadVideoParams {
    pub upload_id: String,
    pub path: String,
    pub mime_type: String,
    pub access_token: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UploadOutcome {
    pub media_id: String,
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
                        "X rejected the request with status {}: {}",
                        status.as_u16(),
                        body
                    ),
                })
            } else {
                Outcome::Fatal(UploadError::Fatal {
                    message: format!("X upload failed with status {}: {}", status.as_u16(), body),
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
                    "X request failed fatally: {}",
                    crate::logging::describe_error(&error)
                );
                return Err(error);
            }
            Outcome::Retry(reason) => {
                log::warn!(
                    "X request attempt {} of {} failed: {}",
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
        "X request gave up after {} attempts: {}",
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

fn media_category_for(_mime_type: &str) -> &'static str {
    "tweet_video"
}

async fn initiate_upload(
    client: &reqwest::Client,
    access_token: &str,
    total_size: u64,
    mime_type: &str,
) -> Result<String, UploadError> {
    let response = with_retry(|| {
        let form = reqwest::multipart::Form::new()
            .text("command", "INIT")
            .text("total_bytes", total_size.to_string())
            .text("media_type", mime_type.to_string())
            .text("media_category", media_category_for(mime_type));
        client
            .post(UPLOAD_ENDPOINT)
            .bearer_auth(access_token)
            .multipart(form)
            .send()
    })
    .await?;

    let body: serde_json::Value = response.json().await.map_err(|error| UploadError::Network {
        message: error.to_string(),
    })?;

    body.get("data")
        .and_then(|data| data.get("id"))
        .and_then(|value| value.as_str())
        .map(|value| value.to_string())
        .ok_or_else(|| UploadError::Fatal {
            message: "X init response did not include a media id".to_string(),
        })
}

async fn append_chunk(
    client: &reqwest::Client,
    access_token: &str,
    media_id: &str,
    segment_index: u32,
    chunk: Vec<u8>,
) -> Result<(), UploadError> {
    with_retry(|| {
        let form = reqwest::multipart::Form::new()
            .text("command", "APPEND")
            .text("media_id", media_id.to_string())
            .text("segment_index", segment_index.to_string())
            .part(
                "media",
                reqwest::multipart::Part::bytes(chunk.clone()).file_name("chunk"),
            );
        client
            .post(UPLOAD_ENDPOINT)
            .bearer_auth(access_token)
            .multipart(form)
            .send()
    })
    .await?;
    Ok(())
}

async fn finalize_upload(
    client: &reqwest::Client,
    access_token: &str,
    media_id: &str,
) -> Result<(), UploadError> {
    with_retry(|| {
        let form = reqwest::multipart::Form::new()
            .text("command", "FINALIZE")
            .text("media_id", media_id.to_string());
        client
            .post(UPLOAD_ENDPOINT)
            .bearer_auth(access_token)
            .multipart(form)
            .send()
    })
    .await?;
    Ok(())
}

fn cancellation_flag(state: &State<XUploadCancellations>, upload_id: &str) -> Arc<AtomicBool> {
    let mut registry = state.0.lock().expect("upload cancellation lock poisoned");
    registry
        .entry(upload_id.to_string())
        .or_insert_with(|| Arc::new(AtomicBool::new(false)))
        .clone()
}

fn clear_cancellation(state: &State<XUploadCancellations>, upload_id: &str) {
    state.0.lock().expect("upload cancellation lock poisoned").remove(upload_id);
}

#[tauri::command]
pub fn cancel_x_upload(upload_id: String, state: State<XUploadCancellations>) {
    log::info!("cancelling X upload {upload_id}");
    if let Some(flag) = state.0.lock().expect("upload cancellation lock poisoned").get(&upload_id) {
        flag.store(true, Ordering::SeqCst);
    }
}

#[tauri::command]
pub async fn upload_video_x(
    params: UploadVideoParams,
    state: State<'_, XUploadCancellations>,
    on_progress: Channel<UploadProgressEvent>,
) -> Result<UploadOutcome, UploadError> {
    let cancelled = cancellation_flag(&state, &params.upload_id);

    log::info!(
        "X upload {} starting for {} ({})",
        params.upload_id,
        params.path,
        params.mime_type
    );

    let result = run_upload(&params, &cancelled, &on_progress).await;
    clear_cancellation(&state, &params.upload_id);

    match &result {
        Ok(_) => log::info!("X upload {} finished", params.upload_id),
        Err(error) => log::error!(
            "X upload {} failed: {}",
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

    let media_id = initiate_upload(&client, &params.access_token, total_size, &params.mime_type).await?;

    let mut offset = 0u64;
    let mut segment_index = 0u32;

    while offset < total_size {
        if cancelled.load(Ordering::SeqCst) {
            log::info!(
                "X upload {} cancelled at offset {}",
                params.upload_id,
                offset
            );
            return Err(UploadError::Cancelled {
                message: "upload cancelled".to_string(),
            });
        }

        let this_chunk_size = PREFERRED_CHUNK_SIZE.min(total_size - offset);
        let chunk = read_chunk(&params.path, offset, this_chunk_size)
            .map_err(|message| UploadError::Fatal { message })?;

        append_chunk(&client, &params.access_token, &media_id, segment_index, chunk).await?;

        offset += this_chunk_size;
        segment_index += 1;

        log::debug!(
            "X upload {} progressed to {} of {} bytes",
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

    finalize_upload(&client, &params.access_token, &media_id).await?;

    Ok(UploadOutcome { media_id })
}
