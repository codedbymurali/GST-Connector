import io
import json
import re
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
from config_and_samples import standardize_columns

def sanitizeTallyXml(rawXml: str) -> str:
    """Strips illegal control characters and fixes unescaped ampersands from Tally XML responses."""
    if not rawXml:
        return ""
    cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', rawXml)
    cleaned = re.sub(r'&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', cleaned)
    return cleaned

def discover_tally_port() -> int:
    """Scans local ports 9000 to 9015 to find an active Tally Prime instance."""
    for port in range(9000, 9016):
        try:
            url = f"http://127.0.0.1:{port}"
            payload = "<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER><BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>List of Companies</REPORTNAME></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"
            res = requests.post(url, data=payload, timeout=0.8)
            if res.status_code == 200 and "<COMPANY" in res.text:
                return port
        except Exception:
            continue
    return 9000  # Default fallback port

def fetch_tally_vouchers_chunked(from_date: str, to_date: str) -> pd.DataFrame:
    """Fetches vouchers in monthly chunks to prevent Tally from freezing."""
    port = discover_tally_port()
    base_url = f"http://127.0.0.1:{port}"
    
    start_dt = datetime.strptime(from_date, "%Y-%m-%d")
    end_dt = datetime.strptime(to_date, "%Y-%m-%d")
    
    all_rows = []
    curr_start = start_dt
    
    while curr_start <= end_dt:
        curr_end = min(curr_start + timedelta(days=30), end_dt)
        f_str = curr_start.strftime("%Y%m%d")
        t_str = curr_end.strftime("%Y%m%d")
        
        xml_payload = f"""
        <ENVELOPE>
            <HEADER>
                <TALLYREQUEST>Export Data</TALLYREQUEST>
            </HEADER>
            <BODY>
                <EXPORTDATA>
                    <REQUESTDESC>
                        <REPORTNAME>Voucher Register</REPORTNAME>
                        <STATICVARIABLES>
                            <SVFROMDATE>{f_str}</SVFROMDATE>
                            <SVTODATE>{t_str}</SVTODATE>
                            <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                        </STATICVARIABLES>
                    </REQUESTDESC>
                </EXPORTDATA>
            </BODY>
        </ENVELOPE>
        """
        try:
            res = requests.post(base_url, data=xml_payload, timeout=5)
            if res.status_code == 200:
                clean_xml = sanitizeTallyXml(res.text)
                root = ET.fromstring(clean_xml)
                for vch in root.findall(".//VOUCHER"):
                    vtype = vch.attrib.get("VCHTYPE", "")
                    if "PURCHASE" not in vtype.upper() and "JOURNAL" not in vtype.upper():
                        continue
                    all_rows.append({
                        "GSTIN": vch.findtext("PARTYGSTIN", ""),
                        "Supplier_Name": vch.findtext("PARTYLEDGERNAME", ""),
                        "Invoice_No": vch.findtext("REFERENCE", "") or vch.findtext("VOUCHERNUMBER", ""),
                        "Invoice_Date": vch.findtext("REFERENCEDATE", "") or vch.findtext("DATE", ""),
                        "Taxable_Value": float(vch.findtext("AMOUNT", 0.0) or 0.0),
                        "IGST": 0.0, "CGST": 0.0, "SGST": 0.0,
                        "Doc_Type": "INV"
                    })
        except Exception:
            pass
        
        curr_start = curr_end + timedelta(days=1)
        
    if not all_rows:
        return pd.DataFrame()
    return standardize_columns(pd.DataFrame(all_rows))

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
        root = ET.fromstring(sanitizeTallyXml(file_bytes.decode("utf-8", errors="ignore")))
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
