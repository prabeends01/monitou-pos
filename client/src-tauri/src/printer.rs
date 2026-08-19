use std::time::Duration;

use escpos::driver::NetworkDriver;
use escpos::printer::Printer;
use escpos::utils::Protocol;
use serde::{Deserialize, Serialize};

/// One printed receipt line: SKU/name and qty at unit price, mirrors a `SaleItem`.
#[derive(Deserialize)]
pub struct ReceiptLine {
    pub name: String,
    pub qty_base_units: i64,
    pub unit_price: String,
}

/// Everything the printer needs to render a receipt — kept flat (no nested
/// Sale/SaleItem types) so this command has no dependency on the backend's
/// JSON shape beyond what's printed.
#[derive(Deserialize)]
pub struct ReceiptPayload {
    pub invoice_number: String,
    pub created_at_client: String,
    pub payment_mode: String,
    pub gst_amount: String,
    pub total_amount: String,
    pub items: Vec<ReceiptLine>,
}

#[derive(Serialize)]
pub struct PrintResult {
    pub ok: bool,
    pub error: Option<String>,
}

/// Print a receipt to a network ESC/POS thermal printer (host:port, typically
/// port 9100). USB/serial support was dropped from the crate feature set to
/// keep the Windows build simple — network printers are the common case for
/// shop POS terminals. See CLAUDE.md Section 9 for the fallback plan
/// (PDF-invoice-via-print-dialog) if network printing doesn't fit a given
/// shop's hardware.
#[tauri::command]
pub fn print_receipt(host: String, port: u16, receipt: ReceiptPayload) -> PrintResult {
    match print_receipt_inner(&host, port, &receipt) {
        Ok(()) => PrintResult { ok: true, error: None },
        Err(err) => PrintResult { ok: false, error: Some(err.to_string()) },
    }
}

fn print_receipt_inner(host: &str, port: u16, receipt: &ReceiptPayload) -> escpos::errors::Result<()> {
    let driver = NetworkDriver::open(host, port, Some(Duration::from_secs(3)))?;
    let mut printer = Printer::new(driver, Protocol::default(), None);

    printer
        .init()?
        .writeln("Monitou Spare Parts")?
        .writeln(&format!("Invoice: {}", receipt.invoice_number))?
        .writeln(&format!("Date: {}", receipt.created_at_client))?
        .writeln("--------------------------------")?;

    for line in &receipt.items {
        printer.writeln(&format!("{}  x{}  {}", line.name, line.qty_base_units, line.unit_price))?;
    }

    printer
        .writeln("--------------------------------")?
        .writeln(&format!("GST: {}", receipt.gst_amount))?
        .writeln(&format!("TOTAL: {}", receipt.total_amount))?
        .writeln(&format!("Payment: {}", receipt.payment_mode))?
        .feed()?
        .cut()?
        .print()?;

    Ok(())
}
