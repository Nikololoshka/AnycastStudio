use tauri_plugin_log::{Target, TargetKind, TimezoneStrategy};

const LOG_FILE_NAME: &str = "multiposter";
const MAX_LOG_FILE_SIZE: u128 = 5 * 1024 * 1024;

fn level() -> log::LevelFilter {
    if cfg!(debug_assertions) {
        log::LevelFilter::Debug
    } else {
        log::LevelFilter::Info
    }
}

pub fn plugin<R: tauri::Runtime>() -> tauri::plugin::TauriPlugin<R> {
    tauri_plugin_log::Builder::new()
        .targets([
            Target::new(TargetKind::Stdout),
            Target::new(TargetKind::LogDir {
                file_name: Some(LOG_FILE_NAME.to_string()),
            }),
        ])
        .level(level())
        .max_file_size(MAX_LOG_FILE_SIZE)
        .timezone_strategy(TimezoneStrategy::UseLocal)
        .build()
}

pub fn redact(secret: &str) -> String {
    format!("<redacted:{} chars>", secret.chars().count())
}

pub fn redact_url(url: &str) -> String {
    match url.split_once('?') {
        Some((base, query)) => format!("{base}?<redacted:{} chars>", query.chars().count()),
        None => url.to_string(),
    }
}

pub fn describe_error<E: serde::Serialize>(error: &E) -> String {
    let Ok(serde_json::Value::Object(fields)) = serde_json::to_value(error) else {
        return "unknown error".to_string();
    };
    let kind = fields.get("type").and_then(|value| value.as_str()).unwrap_or("unknown");
    let message = fields
        .get("message")
        .and_then(|value| value.as_str())
        .unwrap_or("no message");
    format!("{kind}: {message}")
}
