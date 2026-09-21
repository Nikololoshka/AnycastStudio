import { invoke } from '@tauri-apps/api/core';

export function openAppDataFolder(): Promise<void> {
  return invoke('open_app_data_folder');
}
