import { load, type Store } from '@tauri-apps/plugin-store';

const STORE_FILE = 'app-state.json';

let storePromise: Promise<Store> | undefined;

function getStore(): Promise<Store> {
  if (!storePromise) {
    storePromise = load(STORE_FILE, { autoSave: true });
  }
  return storePromise;
}

export async function getPersisted<T>(key: string): Promise<T | undefined> {
  const store = await getStore();
  return store.get<T>(key);
}

export async function setPersisted<T>(key: string, value: T): Promise<void> {
  const store = await getStore();
  await store.set(key, value);
}

export async function deletePersisted(key: string): Promise<void> {
  const store = await getStore();
  await store.delete(key);
}
