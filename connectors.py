import io
import json
import xml.etree.ElementTree as ET
import requests
import pandas as pd
from config_and_samples import standardize_columns

def parse_uploaded_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
    fname = filename.lower()
    if fname.endswith(".json"):
        raw = json.loads(file_bytes.decode("utf-8"))
        rows = []
        b2b = raw.get("data", {}).get("docdata", {}).get("b2b", []) or raw.get("b2b", [])
        for supplier in b2b:
            ctin = supplier.get("ctin", "")
            trdnm = supplier.get("trdnm", "")
            for inv in supplier.get("inv", []):
                txval = inv.get("txval", 0.0)
                igst, cgst, sgst = inv.get("igst", 0.0), inv.get("cgst", 0.0), inv.get("sgst", 0.0)
                if "itms" in inv and not txval:
                    for itm in inv["itms"]:
                        det = itm.get("itm_det", {})
                        txval += det.get("txval", 0.0)
                        igst += det.get("iamt", 0.0)
                        cgst += det.get("camt", 0.0)
                        sgst += det.get("samt", 0.0)
                rows.append({
                    "GSTIN": ctin, "Supplier_Name": trdnm, "Invoice_No": inv.get("inum", ""),
                    "Invoice_Date": inv.get("idt", ""), "Taxable_Value": txval,
                    "IGST": igst, "CGST": cgst, "SGST": sgst, "Doc_Type": "INV"
                })
        return standardize_columns(pd.DataFrame(rows))

    if fname.endswith(".xml"):
        root = ET.fromstring(file_bytes.decode("utf-8", errors="ignore"))
        rows = []
        for vch in root.findall(".//VOUCHER"):
            vtype = vch.attrib.get("VCHTYPE", "")
            if "PURCHASE" not in vtype.upper() and "CREDIT" not in vtype.upper():
                continue
            rows.append({
                "GSTIN": vch.findtext("PARTYGSTIN", ""),
                "Supplier_Name": vch.findtext("PARTYLEDGERNAME", ""),
                "Invoice_No": vch.findtext("REFERENCE", "") or vch.findtext("VOUCHERNUMBER", ""),
                "Invoice_Date": vch.findtext("REFERENCEDATE", "") or vch.findtext("DATE", ""),
                "Taxable_Value": 0.0, "IGST": 0.0, "CGST": 0.0, "SGST": 0.0,
                "Doc_Type": "CN" if "CREDIT" in vtype.upper() else "INV"
            })
        return standardize_columns(pd.DataFrame(rows))

    if fname.endswith(".csv"):
        return standardize_columns(pd.read_csv(io.BytesIO(file_bytes)))
    return standardize_columns(pd.read_excel(io.BytesIO(file_bytes)))

def fetch_erpnext_invoices(url: str, key: str, secret: str, from_date: str, to_date: str) -> pd.DataFrame:
    api_url = f"{url.rstrip('/')}/api/resource/Purchase Invoice"
    headers = {"Authorization": f"token {key}:{secret}"}
    fields = json.dumps(["name", "supplier_name", "supplier_gstin", "bill_no", "bill_date", "posting_date", "net_total", "total_taxes_and_charges", "is_return"])
    filters = json.dumps([["Purchase Invoice", "docstatus", "=", 1], ["Purchase Invoice", "posting_date", ">=", from_date], ["Purchase Invoice", "posting_date", "<=", to_date]])
    r = requests.get(api_url, headers=headers, params={"fields": fields, "filters": filters, "limit_page_length": 1000}, timeout=15)
    r.raise_for_status()
    rows = [{
        "GSTIN": d.get("supplier_gstin", ""),
        "Supplier_Name": d.get("supplier_name", ""),
        "Invoice_No": d.get("bill_no") or d.get("name", ""),
        "Invoice_Date": d.get("bill_date") or d.get("posting_date", ""),
        "Taxable_Value": d.get("net_total", 0.0),
        "IGST": d.get("total_taxes_and_charges", 0.0),
        "CGST": 0.0, "SGST": 0.0,
        "Doc_Type": "CN" if d.get("is_return") else "INV"
    } for d in r.json().get("data", [])]
    return standardize_columns(pd.DataFrame(rows))
