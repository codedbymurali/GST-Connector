# modules/sales_register.py
# CA GST Suite Pro - Module 1: Sales Reconciliation & GSTR-1 Engine

import pandas as pd

class SalesRegisterEngine:
    def __init__(self, erp_sales_df: pd.DataFrame, gstr1_df: pd.DataFrame):
        """
        Initializes the engine with Sales Register (Books/Tally) and GSTR-1 Portal data.
        """
        self.erp_sales_df = erp_sales_df
        self.gstr1_df = gstr1_df

    def process_sales_reconciliation(self, tolerance: float = 2.0) -> pd.DataFrame:
        """
        Compares Books Outward Supplies with GSTR-1 filed returns,
        identifying exact matches, value differences, and unfiled invoices.
        """
        if self.erp_sales_df.empty and self.gstr1_df.empty:
            return pd.DataFrame()

        b_df = self.erp_sales_df.copy()
        p_df = self.gstr1_df.copy()

        # Normalize columns and clean invoice numbers
        for df in [b_df, p_df]:
            df["GSTIN"] = df["GSTIN"].astype(str).str.upper().str.strip()
            df["Invoice_No"] = df["Invoice_No"].astype(str).str.upper().str.strip()
            df["Total_Tax"] = df["IGST"] + df["CGST"] + df["SGST"]

        results = []
        used_b, used_p = set(), set()

        # Map GSTR-1 portal invoices by Customer GSTIN & Invoice Number
        portal_map = {}
        for idx, row in p_df.iterrows():
            portal_map.setdefault((row["GSTIN"], row["Invoice_No"]), []).append((idx, row))

        # Pass 1: Match by GSTIN and Invoice Number
        for b_idx, b_row in b_df.iterrows():
            key = (b_row["GSTIN"], b_row["Invoice_No"])
            if key in portal_map:
                for p_idx, p_row in portal_map[key]:
                    if p_idx in used_p:
                        continue
                    
                    used_b.add(b_idx)
                    used_p.add(p_idx)
                    
                    diff = round(b_row["Total_Tax"] - p_row["Total_Tax"], 2)
                    status = "Matched" if abs(diff) <= tolerance else "Tax Value Differed"
                    
                    results.append({
                        "Customer_GSTIN": b_row["GSTIN"],
                        "Customer_Name": b_row["Supplier_Name"] or p_row["Supplier_Name"],
                        "ERP_Invoice_No": b_row["Invoice_No"],
                        "GSTR1_Invoice_No": p_row["Invoice_No"],
                        "Invoice_Date": b_row["Invoice_Date"] or p_row["Invoice_Date"],
                        "ERP_Tax": round(b_row["Total_Tax"], 2),
                        "GSTR1_Tax": round(p_row["Total_Tax"], 2),
                        "Tax_Difference": diff,
                        "Status": status,
                        "Suggested_Action": "All Clear - Declared Correctly" if status == "Matched" else "Reconcile Tax Head Mismatch"
                    })
                    break

        # Pass 2: Leftovers in ERP (Missing in GSTR-1 / Unfiled Outward Invoices)
        for b_idx, b_row in b_df.iterrows():
            if b_idx not in used_b:
                results.append({
                    "Customer_GSTIN": b_row["GSTIN"],
                    "Customer_Name": b_row["Supplier_Name"],
                    "ERP_Invoice_No": b_row["Invoice_No"],
                    "GSTR1_Invoice_No": "-",
                    "Invoice_Date": b_row["Invoice_Date"],
                    "ERP_Tax": round(b_row["Total_Tax"], 2),
                    "GSTR1_Tax": 0.0,
                    "Tax_Difference": round(b_row["Total_Tax"], 2),
                    "Status": "Missing in GSTR-1",
                    "Suggested_Action": "Report in Next GSTR-1 Amendment (1A/9)"
                })

        # Pass 3: Leftovers in GSTR-1 (Declared in Portal but Missing in Books)
        for p_idx, p_row in p_df.iterrows():
            if p_idx not in used_p:
                results.append({
                    "Customer_GSTIN": p_row["GSTIN"],
                    "Customer_Name": p_row["Supplier_Name"],
                    "ERP_Invoice_No": "-",
                    "GSTR1_Invoice_No": p_row["Invoice_No"],
                    "Invoice_Date": p_row["Invoice_Date"],
                    "ERP_Tax": 0.0,
                    "GSTR1_Tax": round(p_row["Total_Tax"], 2),
                    "Tax_Difference": round(-p_row["Total_Tax"], 2),
                    "Status": "Missing in Books (ERP)",
                    "Suggested_Action": "Pass Adjustment Entry in Tally"
                })

        return pd.DataFrame(results)

    def generate_sales_summary(self, reconciled_df: pd.DataFrame) -> dict:
        """
        Generates clean summary analytics for the Sales Dashboard.
        """
        if reconciled_df.empty:
            return {"total_invoices": 0, "matched_tax": 0.0, "unfiled_tax": 0.0}

        total_inv = len(reconciled_df)
        matched_tax = float(reconciled_df[reconciled_df["Status"] == "Matched"]["ERP_Tax"].sum())
        unfiled_tax = float(reconciled_df[reconciled_df["Status"] == "Missing in GSTR-1"]["ERP_Tax"].sum())

        return {
            "total_invoices": total_inv,
            "matched_tax": matched_tax,
            "unfiled_tax": unfiled_tax
        }