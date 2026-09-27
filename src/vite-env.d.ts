/// <reference types="vite/client" />

interface ImportMetaEnv {
  /* Base URL of the FastAPI backend. In development the Vite proxy forwards
     `/api` to it, so this can stay unset and requests stay same-origin — which
     keeps the HttpOnly session cookies first-party. Set it only when the API
     lives on a different origin (see `vite.config.ts` for the dev proxy). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
