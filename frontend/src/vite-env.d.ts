/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_YOUTUBE_CLIENT_ID: string;
  readonly VITE_YOUTUBE_CLIENT_SECRET: string;
  readonly VITE_TIKTOK_CLIENT_KEY: string;
  readonly VITE_TIKTOK_CLIENT_SECRET: string;
  readonly VITE_FACEBOOK_BROKER_TOKEN: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
