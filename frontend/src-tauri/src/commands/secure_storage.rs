const SERVICE_NAME: &str = "multiposter";

fn entry_for(account_id: &str) -> Result<keyring::Entry, String> {
    keyring::Entry::new(SERVICE_NAME, account_id).map_err(|error| {
        log::error!("keyring entry unavailable for account {account_id}: {error}");
        error.to_string()
    })
}

#[tauri::command]
pub fn store_credential(account_id: String, secret: String) -> Result<(), String> {
    log::info!(
        "storing credential for account {account_id} ({})",
        crate::logging::redact(&secret)
    );
    entry_for(&account_id)?
        .set_password(&secret)
        .map_err(|error| {
            log::error!("failed to store credential for account {account_id}: {error}");
            error.to_string()
        })
}

#[tauri::command]
pub fn get_credential(account_id: String) -> Result<String, String> {
    log::debug!("reading credential for account {account_id}");
    entry_for(&account_id)?.get_password().map_err(|error| {
        log::warn!("failed to read credential for account {account_id}: {error}");
        error.to_string()
    })
}

#[tauri::command]
pub fn delete_credential(account_id: String) -> Result<(), String> {
    log::info!("deleting credential for account {account_id}");
    match entry_for(&account_id)?.delete_credential() {
        Ok(()) => Ok(()),
        Err(keyring::Error::NoEntry) => {
            log::debug!("no stored credential for account {account_id}");
            Ok(())
        }
        Err(error) => {
            log::error!("failed to delete credential for account {account_id}: {error}");
            Err(error.to_string())
        }
    }
}
