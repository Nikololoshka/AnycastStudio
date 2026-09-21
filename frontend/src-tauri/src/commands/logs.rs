use serde::Deserialize;
use tauri::{AppHandle, Manager};
use tauri_plugin_opener::OpenerExt;

fn logs_directory(app: &AppHandle) -> Result<std::path::PathBuf, String> {
    let directory = app.path().app_log_dir().map_err(|error| error.to_string())?;
    std::fs::create_dir_all(&directory).map_err(|error| error.to_string())?;
    Ok(directory)
}

#[tauri::command]
pub fn get_logs_directory(app: AppHandle) -> Result<String, String> {
    Ok(logs_directory(&app)?.to_string_lossy().to_string())
}

#[tauri::command]
pub fn open_logs_folder(app: AppHandle) -> Result<(), String> {
    let directory = logs_directory(&app)?;
    log::info!("opening logs folder {}", directory.display());
    app.opener()
        .open_path(directory.to_string_lossy().to_string(), None::<&str>)
        .map_err(|error| {
            log::error!("failed to open logs folder: {error}");
            error.to_string()
        })
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum FrontendLogLevel {
    Debug,
    Info,
    Warn,
    Error,
}

impl From<&FrontendLogLevel> for log::Level {
    fn from(level: &FrontendLogLevel) -> Self {
        match level {
            FrontendLogLevel::Debug => log::Level::Debug,
            FrontendLogLevel::Info => log::Level::Info,
            FrontendLogLevel::Warn => log::Level::Warn,
            FrontendLogLevel::Error => log::Level::Error,
        }
    }
}

#[tauri::command]
pub fn write_frontend_log(level: FrontendLogLevel, target: String, message: String) {
    log::log!(target: &format!("frontend::{target}"), log::Level::from(&level), "{message}");
}
