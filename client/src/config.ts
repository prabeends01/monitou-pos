export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  terminalId: import.meta.env.VITE_TERMINAL_ID ?? "T1",
  invoiceSeries: import.meta.env.VITE_INVOICE_SERIES ?? "T1",
  printerHost: import.meta.env.VITE_PRINTER_HOST ?? "",
  printerPort: Number(import.meta.env.VITE_PRINTER_PORT ?? 9100),
};
