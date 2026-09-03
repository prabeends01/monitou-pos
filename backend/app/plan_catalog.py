"""Single source of truth for the plan/feature/limit commercial data.

This is the ONLY place plan pricing, the feature catalog, and the
plan -> feature / plan -> limit mappings are defined. Nothing else in the
codebase (backend or frontend) should hard-code a feature code against a
plan code, a price, or a limit value — read it from the seeded `plans`,
`features`, `plan_features`, `plan_limits` tables via the entitlement /
usage-limit services instead.

Editing commercial terms after go-live is a platform-admin/DB task (Stage 12),
not a code change — this module only supplies the *initial* seed.

Run: uv run python -m app.seed_plans
"""

PLAN_CODES = ("BASIC", "ESSENTIAL", "ENTERPRISE")

PLANS = {
    "BASIC": {
        "name": "Basic",
        "description": "Core Inventory & Business Operations — for small "
        "businesses moving away from Excel/manual inventory.",
        "setup_price": "250000.00",
        "annual_amc": "60000.00",
    },
    "ESSENTIAL": {
        "name": "Essential",
        "description": "Complete Inventory & Operations Automation — the "
        "recommended/default commercial package.",
        "setup_price": "350000.00",
        "annual_amc": "90000.00",
    },
    "ENTERPRISE": {
        "name": "Enterprise",
        "description": "Advanced Multi-Location Inventory & Operations Platform.",
        "setup_price": "500000.00",
        "annual_amc": "150000.00",
    },
}

# limit_code -> {plan_code: value}. Read by services/usage_limits.py.
PLAN_LIMITS: dict[str, dict[str, int]] = {
    "MAX_USERS": {"BASIC": 5, "ESSENTIAL": 15, "ENTERPRISE": 30},
    "MAX_BRANCHES": {"BASIC": 1, "ESSENTIAL": 2, "ENTERPRISE": 5},
    "MAX_WAREHOUSES": {"BASIC": 1, "ESSENTIAL": 2, "ENTERPRISE": 5},
    "MAX_SKUS": {"BASIC": 5000, "ESSENTIAL": 15000, "ENTERPRISE": 50000},
}

# limit_code -> backup retention days, informational (enforced by the backup
# job/infra, not by check_limit) but seeded alongside for the Plan page.
BACKUP_RETENTION_DAYS = {"BASIC": 7, "ESSENTIAL": 15, "ENTERPRISE": 30}

# (code, name, module) — feature_type defaults to "core" for all; platform
# admin can flip specific codes to "addon" later without a schema change.
FEATURES: list[tuple[str, str, str]] = [
    # --- inventory / catalog ---
    ("PRODUCT_MASTER", "Product Master", "inventory_catalog"),
    ("CATEGORY_MANAGEMENT", "Category Management", "inventory_catalog"),
    ("BRAND_MANAGEMENT", "Brand Management", "inventory_catalog"),
    ("UOM_MANAGEMENT", "Unit of Measure Management", "inventory_catalog"),
    ("HSN_GST", "HSN / GST Codes", "inventory_catalog"),
    ("PRODUCT_IMAGES", "Product Images", "inventory_catalog"),
    ("DOCUMENT_ATTACHMENTS", "Document Attachments", "inventory_catalog"),
    ("EXCEL_BULK_IMPORT", "Excel Bulk Import", "inventory_catalog"),
    ("MINIMUM_STOCK", "Minimum Stock", "inventory_catalog"),
    ("REORDER_LEVEL", "Reorder Level", "inventory_catalog"),
    ("LOW_STOCK_ALERT", "Low Stock Alert", "inventory_catalog"),
    ("OUT_OF_STOCK_ALERT", "Out of Stock Alert", "inventory_catalog"),
    ("INVENTORY_VALUATION", "Inventory Valuation", "inventory_catalog"),
    ("STOCK_LEDGER", "Stock Ledger", "inventory_catalog"),
    ("STOCK_ADJUSTMENT", "Stock Adjustment", "inventory_catalog"),
    ("MACHINE_COMPATIBILITY", "Machine Compatibility", "inventory_catalog"),
    ("BATCH_SERIAL_TRACKING", "Batch / Serial Tracking", "inventory_catalog"),
    # --- warehouse ---
    ("WAREHOUSE_MANAGEMENT", "Warehouse Management", "warehouse"),
    ("WAREHOUSE_STOCK", "Warehouse Stock", "warehouse"),
    ("STORAGE_LOCATION", "Storage Location", "warehouse"),
    ("RACK_BIN_MANAGEMENT", "Rack / Bin Management", "warehouse"),
    ("INTER_WAREHOUSE_TRANSFER", "Inter-Warehouse Transfer", "warehouse"),
    ("TRANSFER_APPROVAL", "Transfer Approval", "warehouse"),
    ("IN_TRANSIT_INVENTORY", "In-Transit Inventory", "warehouse"),
    ("DESTINATION_RECEIPT", "Destination Receipt", "warehouse"),
    # --- purchase ---
    ("VENDOR_MASTER", "Vendor Master", "purchase"),
    ("VENDOR_DOCUMENTS", "Vendor Documents", "purchase"),
    ("VENDOR_PURCHASE_HISTORY", "Vendor Purchase History", "purchase"),
    ("PURCHASE_REQUEST", "Purchase Request", "purchase"),
    ("PURCHASE_REQUEST_APPROVAL", "Purchase Request Approval", "purchase"),
    ("PURCHASE_ORDER", "Purchase Order", "purchase"),
    ("PURCHASE_ORDER_APPROVAL", "Purchase Order Approval", "purchase"),
    ("PARTIAL_PO_RECEIPT", "Partial PO Receipt", "purchase"),
    ("GRN", "Goods Receipt Note", "purchase"),
    ("PARTIAL_GRN", "Partial GRN", "purchase"),
    ("DAMAGED_REJECTED_GRN", "Damaged/Rejected GRN", "purchase"),
    ("VENDOR_RETURN", "Vendor Return", "purchase"),
    ("VENDOR_PERFORMANCE", "Vendor Performance", "purchase"),
    # --- sales ---
    ("CUSTOMER_MASTER", "Customer Master", "sales"),
    ("BASIC_SALES_ORDER", "Basic Sales Order", "sales"),
    ("SALES_QUOTATION", "Sales Quotation", "sales"),
    ("QUOTATION_PDF", "Quotation PDF", "sales"),
    ("QUOTATION_TO_ORDER", "Quotation to Order", "sales"),
    ("STOCK_AVAILABILITY", "Stock Availability", "sales"),
    ("STOCK_RESERVATION", "Stock Reservation", "sales"),
    ("PICK_LIST", "Pick List", "sales"),
    ("DISPATCH_MANAGEMENT", "Dispatch Management", "sales"),
    ("TRANSPORT_DETAILS", "Transport Details", "sales"),
    ("CUSTOMER_RETURN", "Customer Return", "sales"),
    ("SALES_APPROVAL", "Sales Approval", "sales"),
    # --- barcode ---
    ("BARCODE_GENERATION", "Barcode Generation", "barcode"),
    ("QR_GENERATION", "QR Generation", "barcode"),
    ("BARCODE_LABEL_PRINTING", "Barcode Label Printing", "barcode"),
    ("BARCODE_SCAN", "Barcode Scan", "barcode"),
    ("BARCODE_GRN", "Barcode GRN", "barcode"),
    ("BARCODE_PICKING", "Barcode Picking", "barcode"),
    ("WRONG_PART_VALIDATION", "Wrong Part Validation", "barcode"),
    ("BARCODE_STOCK_VERIFICATION", "Barcode Stock Verification", "barcode"),
    # --- stock verification / analytics ---
    ("PHYSICAL_STOCK_VERIFICATION", "Physical Stock Verification", "stock_analytics"),
    ("STOCK_VARIANCE", "Stock Variance", "stock_analytics"),
    ("ADJUSTMENT_APPROVAL", "Adjustment Approval", "stock_analytics"),
    ("CYCLE_COUNTING", "Cycle Counting", "stock_analytics"),
    ("DAMAGED_STOCK", "Damaged Stock", "stock_analytics"),
    ("QUARANTINE_STOCK", "Quarantine Stock", "stock_analytics"),
    ("INVENTORY_AGEING", "Inventory Ageing", "stock_analytics"),
    ("FAST_MOVING_ANALYSIS", "Fast Moving Analysis", "stock_analytics"),
    ("SLOW_MOVING_ANALYSIS", "Slow Moving Analysis", "stock_analytics"),
    ("DEAD_STOCK_ANALYSIS", "Dead Stock Analysis", "stock_analytics"),
    # --- dashboard ---
    ("BASIC_DASHBOARD", "Basic Dashboard", "dashboard"),
    ("ADVANCED_DASHBOARD", "Advanced Dashboard", "dashboard"),
    ("EXECUTIVE_DASHBOARD", "Executive Dashboard", "dashboard"),
    # --- reports ---
    ("BASIC_REPORTS", "Basic Reports", "reports"),
    ("ADVANCED_REPORTS", "Advanced Reports", "reports"),
    ("CUSTOM_REPORTS", "Custom Reports", "reports"),
    # --- admin / RBAC / audit ---
    ("CUSTOM_ROLES", "Custom Roles", "admin"),
    ("GRANULAR_PERMISSIONS", "Granular Permissions", "admin"),
    ("SINGLE_LEVEL_APPROVAL", "Single Level Approval", "admin"),
    ("MULTI_LEVEL_APPROVAL", "Multi Level Approval", "admin"),
    ("FULL_AUDIT_LOG", "Full Audit Log", "admin"),
    ("ADVANCED_AUDIT_LOG", "Advanced Audit Log", "admin"),
    # --- hr ---
    ("ATTENDANCE_TRACKING", "Attendance Tracking", "hr"),
    ("LEAVE_MANAGEMENT", "Leave Management", "hr"),
    ("TA_DA_CLAIMS", "TA/DA Claims", "hr"),
]

FEATURE_CODES = {code for code, _name, _module in FEATURES}

_BASIC_FEATURES = {
    "PRODUCT_MASTER", "CATEGORY_MANAGEMENT", "BRAND_MANAGEMENT", "UOM_MANAGEMENT",
    "HSN_GST", "MINIMUM_STOCK", "REORDER_LEVEL", "LOW_STOCK_ALERT", "OUT_OF_STOCK_ALERT",
    "INVENTORY_VALUATION", "STOCK_LEDGER", "STOCK_ADJUSTMENT",
    "WAREHOUSE_MANAGEMENT", "WAREHOUSE_STOCK", "STORAGE_LOCATION",
    "VENDOR_MASTER", "VENDOR_PURCHASE_HISTORY", "PURCHASE_ORDER", "GRN",
    "CUSTOMER_MASTER", "BASIC_SALES_ORDER", "STOCK_AVAILABILITY", "DISPATCH_MANAGEMENT",
    "PHYSICAL_STOCK_VERIFICATION", "STOCK_VARIANCE", "DAMAGED_STOCK",
    "BASIC_DASHBOARD", "BASIC_REPORTS",
}

_ESSENTIAL_ADDS = {
    "PRODUCT_IMAGES", "DOCUMENT_ATTACHMENTS", "EXCEL_BULK_IMPORT", "MACHINE_COMPATIBILITY",
    "RACK_BIN_MANAGEMENT",
    "VENDOR_DOCUMENTS", "PURCHASE_REQUEST", "PURCHASE_REQUEST_APPROVAL",
    "PURCHASE_ORDER_APPROVAL", "PARTIAL_PO_RECEIPT", "PARTIAL_GRN", "DAMAGED_REJECTED_GRN",
    "SALES_QUOTATION", "QUOTATION_PDF", "QUOTATION_TO_ORDER", "STOCK_RESERVATION",
    "PICK_LIST", "TRANSPORT_DETAILS",
    "BARCODE_GENERATION", "QR_GENERATION", "BARCODE_LABEL_PRINTING", "BARCODE_SCAN",
    "BARCODE_GRN", "BARCODE_PICKING",
    "ADJUSTMENT_APPROVAL", "INVENTORY_AGEING", "FAST_MOVING_ANALYSIS", "SLOW_MOVING_ANALYSIS",
    "ADVANCED_DASHBOARD", "ADVANCED_REPORTS",
    "CUSTOM_ROLES", "GRANULAR_PERMISSIONS", "SINGLE_LEVEL_APPROVAL", "FULL_AUDIT_LOG",
}

_ENTERPRISE_ADDS = {
    "BATCH_SERIAL_TRACKING",
    "INTER_WAREHOUSE_TRANSFER", "TRANSFER_APPROVAL", "IN_TRANSIT_INVENTORY", "DESTINATION_RECEIPT",
    "VENDOR_RETURN", "VENDOR_PERFORMANCE",
    "CUSTOMER_RETURN", "SALES_APPROVAL",
    "WRONG_PART_VALIDATION", "BARCODE_STOCK_VERIFICATION",
    "CYCLE_COUNTING", "QUARANTINE_STOCK", "DEAD_STOCK_ANALYSIS",
    "MULTI_LEVEL_APPROVAL",
    "EXECUTIVE_DASHBOARD", "CUSTOM_REPORTS", "ADVANCED_AUDIT_LOG",
    "ATTENDANCE_TRACKING", "LEAVE_MANAGEMENT", "TA_DA_CLAIMS",
}

# plan_code -> set of feature codes enabled by default on that plan.
PLAN_FEATURES: dict[str, set[str]] = {
    "BASIC": set(_BASIC_FEATURES),
    "ESSENTIAL": _BASIC_FEATURES | _ESSENTIAL_ADDS,
    "ENTERPRISE": _BASIC_FEATURES | _ESSENTIAL_ADDS | _ENTERPRISE_ADDS,
}

assert PLAN_FEATURES["ENTERPRISE"] == FEATURE_CODES, (
    "every catalog feature must be reachable by at least the Enterprise plan"
)
