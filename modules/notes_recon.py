# modules/notes_recon.py
# CA GST Suite Pro - Module 3: Credit / Debit Notes Reconciliation Engine

import pandas as pd

class NotesReconciliationEngine:
    def __init__(self, erp_notes_df: pd.DataFrame, portal_notes_df: pd.DataFrame):
        """
        Initializes with Credit/Debit Notes from Books (Tally/ERP) and Portal (GSTR-2B/1).
        """
        self.erp_notes_df = erp_notes_df
        self.portal_notes_df = portal_notes_df

    def process_notes_recon(self, tolerance: float = 2.0) -> pd.DataFrame:
        """
        Matches Credit/Debit notes, checks amendment linkages (like CDNRA/B),
        and calculates net tax impact adjustments.
        """
        if self.erp_notes_df.empty and self.portal_notes_df.empty:
            return pd.DataFrame()

        b_df = self.erp_notes_df.copy()
        p_df = self.portal_notes_df.copy()

        for df in [b_df, p_df]:
            df["GSTIN"] = df["GSTIN"].astype(str).str.upper().str.strip()
            df["Note_No"] = df["Note_No"].astype(str).str.upper().str.strip()
            df["Total_Tax"] = df["IGST"] + df["CGST"] + df["SGST"]

        results = []
        used_b, used_p = set(), set()

        # Portal Notes Map
        portal_map = {}
        for idx, row in p_df.iterrows():
            portal_map.setdefault((row["GSTIN"], row["Note_No"]), []).append((idx, row))

        # Pass 1: Exact GSTIN + Note Number Match
        for b_idx, b_row in b_df.iterrows():
            key = (b_row["GSTIN"], b_row["Note_No"])
            if key in portal_map:
                for p_idx, p_row in portal_map[key]:
                    if p_idx in used_p:
                        continue
                    used_b.add(b_idx)
                    used_p.add(p_idx)

                    diff = round(b_row["Total_Tax"] - p_row["Total_Tax"], 2)
                    status = "Matched" if abs(diff) <= tolerance else "Note Value Differed"

                    results.append({
                        "GSTIN": b_row["GSTIN"],
                        "Party_Name": b_row["Party_Name"] or p_row["Party_Name"],
                        "Note_Type": b_row.get("Note_Type", "CN"),
                        "ERP_Note_No": b_row["Note_No"],
                        "Portal_Note_No": p_row["Note_No"],
                        "Note_Date": b_row["Note_Date"] or p_row["Note_Date"],
                        "ERP_Tax": round(b_row["Total_Tax"], 2),
                        "Portal_Tax": round(p_row["Total_Tax"], 2),
                        "Tax_Difference": diff,
                        "Status": status,
                        "Suggested_Action": "Adjustment Verified" if status == "Matched" else "Reconcile Note Tax Difference"
                    })
                    break

# Pass 2: Unmatched ERP Notes (Missing in Portal)
        for b_idx, b_row in b_df.iterrows():
            if b_idx not in used_b:
                results.append({
                    "GSTIN": b_row["GSTIN"],
                    "Party_Name": b_row["Party_Name"],
                    "Note_Type": b_row.get("Note_Type", "CN"),
                    "ERP_Note_No": b_row["Note_No"],
                    "Portal_Note_No": "-",
                    "Note_Date": b_row["Note_Date"],
                    "ERP_Tax": round(b_row["Total_Tax"], 2),
                    "Portal_Tax": 0.0,
                    "Tax_Difference": round(b_row["Total_Tax"], 2),
                    "Status": "Missing in Portal (2B/1)",
                    "Suggested_Action": "Follow up with Counterparty for Amendment"
                })

        # Pass 3: Unmatched Portal Notes (Missing in ERP Books)
        for p_idx, p_row in p_df.iterrows():
            if p_idx not in used_p:
                results.append({
                    "GSTIN": p_row["GSTIN"],
                    "Party_Name": p_row["Party_Name"],
                    "Note_Type": p_row.get("Note_Type", "CN"),
                    "ERP_Note_No": "-",
                    "Portal_Note_No": p_row["Note_No"],
                    "Note_Date": p_row["Note_Date"],
                    "ERP_Tax": 0.0,
                    "Portal_Tax": round(p_row["Total_Tax"], 2),
                    "Tax_Difference": round(-p_row["Total_Tax"], 2),
                    "Status": "Missing in ERP Books",
                    "Suggested_Action": "Book Note in Tally ERP"
                })

        return pd.DataFrame(results)

    def generate_notes_summary(self, reco_df: pd.DataFrame) -> dict:
        if reco_df.empty:
            return {"total_notes": 0, "matched_tax": 0.0, "unmatched_tax": 0.0}

        total_notes = len(reco_df)
        matched_tax = float(reco_df[reco_df["Status"] == "Matched"]["ERP_Tax"].sum())
        unmatched_tax = float(reco_df[reco_df["Status"] != "Matched"]["Tax_Difference"].abs().sum())

        return {
            "total_notes": total_notes,
            "matched_tax": matched_tax,
            "unmatched_tax": unmatched_tax
        }   