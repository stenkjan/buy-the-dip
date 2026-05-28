/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SIGNALS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
