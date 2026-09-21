/// <reference types="vite/client" />

/** Build-time only. No secret may appear here: the bundle is public. */
interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare const __APP_VERSION__: string;
