import re
import pandas as pd

def clean_inv(val: str) -> str:
    if pd.isna(val):
        return ""
    s = str(val).upper().strip()
    for p in ["INV", "GST", "BILL", "FY2526", "FY2627", "2627"]:
        if s.startswith(p):
            s = s[len(p):]
    return re.sub(r'[^A-Z0-9]', '', s).lstrip('0') or '0'

def run_matching_engine(erp_df: pd.DataFrame, portal_df: pd.DataFrame, tolerance: float = 2.0) -> pd.DataFrame:
    if erp_df.empty and portal_df.empty:
        return pd.DataFrame()

    b_df = erp_df.copy()
    p_df = portal_df.copy()

    for d in [b_df, p_df]:
        d["GSTIN"] = d["GSTIN"].astype(str).str.upper().str.strip()
        d["PAN"] = d["GSTIN"].str[2:12]
        d["Clean_Inv"] = d["Invoice_No"].apply(clean_inv)
        d["Total_Tax"] = d["IGST"] + d["CGST"] + d["SGST"]

    results = []
    used_b, used_p = set(), set()

    # PASS 1: Exact/Fuzzy GSTIN + Clean Invoice
    p_map = {}
    for idx, r in p_df.iterrows():
        p_map.setdefault((r["GSTIN"], r["Clean_Inv"]), []).append((idx, r))

    for b_idx, b_row in b_df.iterrows():
        key = (b_row["GSTIN"], b_row["Clean_Inv"])
        if key in p_map:
            for p_idx, p_row in p_map[key]:
                if p_idx not in used_p:
                    used_b.add(b_idx)
                    used_p.add(p_idx)
                    diff = round(b_row["Total_Tax"] - p_row["Total_Tax"], 2)
                    status = "Matched" if abs(diff) <= tolerance else "Value Differed"
                    results.append({
                        "GSTIN": b_row["GSTIN"],
                        "Supplier_Name": b_row["Supplier_Name"] or p_row["Supplier_Name"],
                        "ERP_Invoice_No": b_row["Invoice_No"],
                        "Portal_Invoice_No": p_row["Invoice_No"],
                        "Invoice_Date": b_row["Invoice_Date"] or p_row["Invoice_Date"],
                        "ERP_Taxable": round(b_row["Taxable_Value"], 2),
                        "Portal_Taxable": round(p_row["Taxable_Value"], 2),
                        "ERP_Tax": round(b_row["Total_Tax"], 2),
                        "Portal_Tax": round(p_row["Total_Tax"], 2),
                        "Tax_Difference": diff,
                        "Status": status,
                        "Match_Pass": "Pass 1: Exact/Fuzzy Invoice",
                        "Suggested_Action": "Claim Full ITC" if status == "Matched" else "Verify Bill Difference"
                    })
                    break

    # PASS 2: Same PAN (Cross-State GSTIN)
    p_pan_map = {}
    for idx, r in p_df.iterrows():
        if idx not in used_p:
            p_pan_map.setdefault((r["PAN"], r["Clean_Inv"]), []).append((idx, r))

    for b_idx, b_row in b_df.iterrows():
        if b_idx not in used_b:
            key = (b_row["PAN"], b_row["Clean_Inv"])
            if key in p_pan_map:
                for p_idx, p_row in p_pan_map[key]:
                    if p_idx not in used_p:
                        used_b.add(b_idx)
                        used_p.add(p_idx)
                        diff = round(b_row["Total_Tax"] - p_row["Total_Tax"], 2)
                        results.append({
                            "GSTIN": b_row["GSTIN"],
                            "Supplier_Name": b_row["Supplier_Name"] or p_row["Supplier_Name"],
                            "ERP_Invoice_No": b_row["Invoice_No"],
                            "Portal_Invoice_No": p_row["Invoice_No"],
                            "Invoice_Date": b_row["Invoice_Date"] or p_row["Invoice_Date"],
                            "ERP_Taxable": round(b_row["Taxable_Value"], 2),
                            "Portal_Taxable": round(p_row["Taxable_Value"], 2),
                            "ERP_Tax": round(b_row["Total_Tax"], 2),
                            "Portal_Tax": round(p_row["Total_Tax"], 2),
                            "Tax_Difference": diff,
                            "Status": "Matched",
                            "Match_Pass": f"Pass 2: Same PAN ({p_row['GSTIN']})",
                            "Suggested_Action": "Correct State GSTIN in ERP"
                        })
                        break

    # PASS 3: Exact Amount + GSTIN Match (Invoice Number Typo)
    for b_idx, b_row in b_df.iterrows():
        if b_idx not in used_b:
            cands = p_df[
                (~p_df.index.isin(used_p)) &
                (p_df["GSTIN"] == b_row["GSTIN"]) &
                ((p_df["Total_Tax"] - b_row["Total_Tax"]).abs() <= tolerance) &
                ((p_df["Taxable_Value"] - b_row["Taxable_Value"]).abs() <= 5.0)
            ]
            if not cands.empty:
                p_idx = cands.index[0]
                p_row = cands.loc[p_idx]
                used_b.add(b_idx)
                used_p.add(p_idx)
                results.append({
                    "GSTIN": b_row["GSTIN"],
                    "Supplier_Name": b_row["Supplier_Name"] or p_row["Supplier_Name"],
                    "ERP_Invoice_No": b_row["Invoice_No"],
                    "Portal_Invoice_No": p_row["Invoice_No"],
                    "Invoice_Date": b_row["Invoice_Date"] or p_row["Invoice_Date"],
                    "ERP_Taxable": round(b_row["Taxable_Value"], 2),
                    "Portal_Taxable": round(p_row["Taxable_Value"], 2),
                    "ERP_Tax": round(b_row["Total_Tax"], 2),
                    "Portal_Tax": round(p_row["Total_Tax"], 2),
                    "Tax_Difference": 0.0,
                    "Status": "Matched",
                    "Match_Pass": "Pass 3: Matched by Amount (Inv Typo)",
                    "Suggested_Action": "Update Inv No in ERP"
                })

    # Leftovers: Only in ERP
    for b_idx, b_row in b_df.iterrows():
        if b_idx not in used_b:
            results.append({
                "GSTIN": b_row["GSTIN"],
                "Supplier_Name": b_row["Supplier_Name"],
                "ERP_Invoice_No": b_row["Invoice_No"],
                "Portal_Invoice_No": "-",
                "Invoice_Date": b_row["Invoice_Date"],
                "ERP_Taxable": round(b_row["Taxable_Value"], 2),
                "Portal_Taxable": 0.0,
                "ERP_Tax": round(b_row["Total_Tax"], 2),
                "Portal_Tax": 0.0,
                "Tax_Difference": round(b_row["Total_Tax"], 2),
                "Status": "Only in ERP/Books",
                "Match_Pass": "Unmatched",
                "Suggested_Action": "Hold ITC & Notify Supplier"
            })

    # Leftovers: Only in Portal
    for p_idx, p_row in p_df.iterrows():
        if p_idx not in used_p:
            results.append({
                "GSTIN": p_row["GSTIN"],
                "Supplier_Name": p_row["Supplier_Name"],
                "ERP_Invoice_No": "-",
                "Portal_Invoice_No": p_row["Invoice_No"],
                "Invoice_Date": p_row["Invoice_Date"],
                "ERP_Taxable": 0.0,
                "Portal_Taxable": round(p_row["Taxable_Value"], 2),
                "ERP_Tax": 0.0,
                "Portal_Tax": round(p_row["Total_Tax"], 2),
                "Tax_Difference": round(-p_row["Total_Tax"], 2),
                "Status": "Only in GST Portal",
                "Match_Pass": "Unmatched",
                "Suggested_Action": "Verify Bill & Book in ERP"
            })

    return pd.DataFrame(results)

class PurchaseRegisterEngine:
    def __init__(self, raw_vouchers):
        self.raw_vouchers = raw_vouchers
        self.blocked_keywords = [
            "motor vehicle", "car", "food", "beverages", "club", 
            "membership", "health insurance", "construction", "repair of building"
        ]

    def process_purchase_register(self):
        processed_records = []
        for voucher in self.raw_vouchers:
            invoice_no = voucher.get("invoice_no", "UNKNOWN")
            date = voucher.get("date", "")
            party_name = voucher.get("party_name", "")
            gstin = voucher.get("gstin", "")
            taxable_value = float(voucher.get("taxable_value", 0.0))
            cgst = float(voucher.get("cgst", 0.0))
            sgst = float(voucher.get("sgst", 0.0))
            igst = float(voucher.get("igst", 0.0))
            total_tax = cgst + sgst + igst
            item_description = voucher.get("item_description", "").lower()
            is_rcm = voucher.get("is_rcm", False)

            itc_status = "Eligible ITC"
            for keyword in self.blocked_keywords:
                if keyword in item_description:
                    itc_status = "Ineligible / Blocked ITC (Sec 17(5))"
                    break

            if is_rcm:
                itc_status = "RCM Liability / Eligible Post Payment"

            processed_records.append({
                "invoice_no": invoice_no,
                "date": date,
                "party_name": party_name,
                "gstin": gstin,
                "taxable_value": taxable_value,
                "total_tax": total_tax,
                "itc_status": itc_status,
                "is_rcm": is_rcm
            })
        return processed_records

    def generate_summary(self, processed_records):
        total_invoices = len(processed_records)
        total_taxable = sum(r["taxable_value"] for r in processed_records)
        eligible_itc_sum = sum(r["total_tax"] for r in processed_records if "Eligible" in r["itc_status"])
        blocked_itc_sum = sum(r["total_tax"] for r in processed_records if "Blocked" in r["itc_status"])

        return {
            "total_invoices": total_invoices,
            "total_taxable_value": total_taxable,
            "eligible_itc": eligible_itc_sum,
            "blocked_itc": blocked_itc_sum
        }
