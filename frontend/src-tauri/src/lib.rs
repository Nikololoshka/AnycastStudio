mod commands;
pub mod logging;

// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(logging::plugin())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_http::init())
        .manage(commands::oauth::OAuthCallbackState::default())
        .manage(commands::youtube_upload::UploadCancellations::default())
        .manage(commands::tiktok_upload::TikTokUploadCancellations::default())
        .manage(commands::x_upload::XUploadCancellations::default())
        .manage(commands::instagram_upload::InstagramUploadCancellations::default())
        .setup(|app| {
            log::info!(
                "Multiposter {} starting",
                app.package_info().version
            );
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            greet,
            commands::logs::open_logs_folder,
            commands::logs::get_logs_directory,
            commands::logs::write_frontend_log,
            commands::filesystem::get_file_metadata,
            commands::filesystem::read_file_chunk,
            commands::filesystem::open_app_data_folder,
            commands::secure_storage::store_credential,
            commands::secure_storage::get_credential,
            commands::secure_storage::delete_credential,
            commands::oauth::start_oauth_callback_server,
            commands::oauth::start_fixed_port_oauth_callback_server,
            commands::oauth::await_oauth_callback,
            commands::oauth::cancel_oauth_callback,
            commands::youtube_upload::upload_video_youtube,
            commands::youtube_upload::cancel_youtube_upload,
            commands::tiktok_upload::upload_video_tiktok,
            commands::tiktok_upload::cancel_tiktok_upload,
            commands::x_upload::upload_video_x,
            commands::x_upload::cancel_x_upload,
            commands::instagram_upload::upload_video_instagram,
            commands::instagram_upload::cancel_instagram_upload
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
