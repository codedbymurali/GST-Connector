import pandas as pd

COLUMN_ALIASES = {
    "GSTIN": ["gstin", "gstin of supplier", "party gstin", "supplier gstin", "gstin/uin", "ctin", "supplier_gstin"],
    "Supplier_Name": ["supplier_name", "trade/legal name", "party name", "supplier name", "vendor name", "trdnm", "supplier"],
    "Invoice_No": ["invoice_no", "invoice number", "inv no", "voucher ref", "bill no", "doc no", "inum", "bill_no", "name"],
    "Invoice_Date": ["invoice_date", "invoice date", "inv date", "bill date", "date", "idt", "bill_date", "posting_date"],
    "Taxable_Value": ["taxable_value", "taxable value", "taxable", "taxable amount", "txval", "net_total"],
    "IGST": ["igst", "integrated tax", "integrated tax(₹)", "igst amount", "iamt"],
    "CGST": ["cgst", "central tax", "central tax(₹)", "cgst amount", "camt"],
    "SGST": ["sgst", "state/ut tax", "state/ut tax(₹)", "sgst amount", "utgst", "samt"],
    "Doc_Type": ["doc_type", "document type", "voucher type", "type", "typ"]
}

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["GSTIN", "Supplier_Name", "Invoice_No", "Invoice_Date", "Taxable_Value", "IGST", "CGST", "SGST", "Doc_Type"])
    col_map = {}
    lower_cols = {str(c).strip().lower(): c for c in df.columns}
    for target_col in COLUMN_ALIASES:
        if target_col not in df.columns:
            for alias in COLUMN_ALIASES[target_col]:
                if alias in lower_cols:
                    col_map[lower_cols[alias]] = target_col
                    break
    df = df.rename(columns=col_map)
    for req in ["GSTIN", "Supplier_Name", "Invoice_No", "Invoice_Date", "Taxable_Value", "IGST", "CGST", "SGST"]:
        if req not in df.columns:
            df[req] = 0.0 if req in ["Taxable_Value", "IGST", "CGST", "SGST"] else ""
    if "Doc_Type" not in df.columns:
        df["Doc_Type"] = "INV"
    for col in ["Taxable_Value", "IGST", "CGST", "SGST"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df

def get_sample_erp_df() -> pd.DataFrame:
    return standardize_columns(pd.DataFrame([
        {"GSTIN": "33AABCU9603R1ZM", "Supplier_Name": "Chennai Steel Pvt Ltd", "Invoice_No": "INV/26-27/00101", "Invoice_Date": "05-10-2026", "Taxable_Value": 50000, "IGST": 0, "CGST": 4500, "SGST": 4500, "Doc_Type": "INV"},
        {"GSTIN": "33AADCS1234F1Z5", "Supplier_Name": "Apex Logistics India", "Invoice_No": "AL-889", "Invoice_Date": "11-10-2026", "Taxable_Value": 20000, "IGST": 3600, "CGST": 0, "SGST": 0, "Doc_Type": "INV"},
        {"GSTIN": "33AAECS5678G1Z1", "Supplier_Name": "Infosys Cloud Services", "Invoice_No": "BLR/992", "Invoice_Date": "15-10-2026", "Taxable_Value": 100000, "IGST": 18000, "CGST": 0, "SGST": 0, "Doc_Type": "INV"},
        {"GSTIN": "33AABCU9603R1ZM", "Supplier_Name": "Chennai Steel Pvt Ltd", "Invoice_No": "9045", "Invoice_Date": "18-10-2026", "Taxable_Value": 12500, "IGST": 0, "CGST": 1125, "SGST": 1125, "Doc_Type": "INV"},
        {"GSTIN": "33AAFCK3321H1Z9", "Supplier_Name": "Kaveri Packaging Solutions", "Invoice_No": "KP-77", "Invoice_Date": "22-10-2026", "Taxable_Value": 8000, "IGST": 0, "CGST": 720, "SGST": 720, "Doc_Type": "INV"},
        {"GSTIN": "33AAHCM4455N1Z8", "Supplier_Name": "Deccan Industrial Tools", "Invoice_No": "DIT/2026/55", "Invoice_Date": "24-10-2026", "Taxable_Value": 40000, "IGST": 0, "CGST": 3600, "SGST": 3600, "Doc_Type": "INV"},
    ]))

def get_sample_portal_df() -> pd.DataFrame:
    return standardize_columns(pd.DataFrame([
        {"GSTIN": "33AABCU9603R1ZM", "Supplier_Name": "Chennai Steel Pvt Ltd", "Invoice_No": "101", "Invoice_Date": "05-10-2026", "Taxable_Value": 50000, "IGST": 0, "CGST": 4500, "SGST": 4500, "Doc_Type": "INV"},
        {"GSTIN": "33AADCS1234F1Z5", "Supplier_Name": "Apex Logistics India", "Invoice_No": "AL-889", "Invoice_Date": "11-10-2026", "Taxable_Value": 20000, "IGST": 3100, "CGST": 0, "SGST": 0, "Doc_Type": "INV"},
        {"GSTIN": "29AAECS5678G1Z2", "Supplier_Name": "Infosys Cloud Services", "Invoice_No": "BLR-0992", "Invoice_Date": "15-10-2026", "Taxable_Value": 100000, "IGST": 18000, "CGST": 0, "SGST": 0, "Doc_Type": "INV"},
        {"GSTIN": "33AABCU9603R1ZM", "Supplier_Name": "Chennai Steel Pvt Ltd", "Invoice_No": "9054", "Invoice_Date": "18-10-2026", "Taxable_Value": 12500, "IGST": 0, "CGST": 1125, "SGST": 1125, "Doc_Type": "INV"},
        {"GSTIN": "33AAGCM9988L1Z3", "Supplier_Name": "Madras Electricals Ltd", "Invoice_No": "ME/404", "Invoice_Date": "25-10-2026", "Taxable_Value": 15000, "IGST": 0, "CGST": 1350, "SGST": 1350, "Doc_Type": "INV"},
        {"GSTIN": "33AAHCM4455N1Z8", "Supplier_Name": "Deccan Industrial Tools", "Invoice_No": "DIT/2026/55", "Invoice_Date": "24-10-2026", "Taxable_Value": 40000, "IGST": 0, "CGST": 3600, "SGST": 3600, "Doc_Type": "INV"},
    ]))
