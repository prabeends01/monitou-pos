/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_TERMINAL_ID?: string;
  readonly VITE_INVOICE_SERIES?: string;
  readonly VITE_PRINTER_HOST?: string;
  readonly VITE_PRINTER_PORT?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
