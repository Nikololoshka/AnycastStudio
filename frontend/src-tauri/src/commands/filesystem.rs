use serde::Serialize;
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use tauri::{AppHandle, Manager};
use tauri_plugin_opener::OpenerExt;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FileMetadata {
    pub size: u64,
    pub mime_type: String,
}

fn guess_mime_type(path: &str) -> String {
    let extension = path.rsplit('.').next().unwrap_or("").to_lowercase();
    match extension.as_str() {
        "mp4" => "video/mp4",
        "mov" => "video/quicktime",
        "webm" => "video/webm",
        "avi" => "video/x-msvideo",
        "mkv" => "video/x-matroska",
        _ => "application/octet-stream",
    }
    .to_string()
}

pub(crate) fn file_size(path: &str) -> Result<u64, String> {
    let file = File::open(path).map_err(|error| {
        log::error!("cannot open {path}: {error}");
        error.to_string()
    })?;
    file.metadata()
        .map_err(|error| {
            log::error!("cannot read metadata of {path}: {error}");
            error.to_string()
        })
        .map(|m| m.len())
}

pub(crate) fn read_chunk(path: &str, offset: u64, size: u64) -> Result<Vec<u8>, String> {
    let mut file = File::open(path).map_err(|error| {
        log::error!("cannot open {path}: {error}");
        error.to_string()
    })?;
    file.seek(SeekFrom::Start(offset)).map_err(|error| {
        log::error!("cannot seek {path} to offset {offset}: {error}");
        error.to_string()
    })?;

    let mut buffer = vec![0u8; size as usize];
    let bytes_read = file.read(&mut buffer).map_err(|error| {
        log::error!("cannot read {size} bytes of {path} at offset {offset}: {error}");
        error.to_string()
    })?;
    buffer.truncate(bytes_read);
    Ok(buffer)
}

#[tauri::command]
pub fn get_file_metadata(path: String) -> Result<FileMetadata, String> {
    log::debug!("reading metadata of {path}");
    Ok(FileMetadata {
        size: file_size(&path)?,
        mime_type: guess_mime_type(&path),
    })
}

#[tauri::command]
pub fn read_file_chunk(path: String, offset: u64, size: u64) -> Result<Vec<u8>, String> {
    read_chunk(&path, offset, size)
}

fn app_data_directory(app: &AppHandle) -> Result<std::path::PathBuf, String> {
    let directory = app.path().app_data_dir().map_err(|error| error.to_string())?;
    std::fs::create_dir_all(&directory).map_err(|error| error.to_string())?;
    Ok(directory)
}

#[tauri::command]
pub fn open_app_data_folder(app: AppHandle) -> Result<(), String> {
    let directory = app_data_directory(&app)?;
    log::info!("opening app data folder {}", directory.display());
    app.opener()
        .open_path(directory.to_string_lossy().to_string(), None::<&str>)
        .map_err(|error| {
            log::error!("failed to open app data folder: {error}");
            error.to_string()
        })
}
