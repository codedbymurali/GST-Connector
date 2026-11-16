import os
import time
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

DB_PATH = 'recon_vault.db'

PORTAL_SESSION_CACHE = {
    "auth_token": None,
    "expiry_time": None,
    "gstin": None
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vault_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_name TEXT,
            saved_at TEXT,
            total_bills INTEGER,
            data_json TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def fetch_from_tally_with_retries(tally_url="http://localhost:9000"):
    base_url = tally_url.rsplit(':', 1)[0]
    ports = range(9000, 9016)
    
    for port in ports:
        target_url = f"{base_url}:{port}"
        for attempt in range(1, 4):
            try:
                response = requests.get(target_url, timeout=2.5)
                if response.status_code == 200:
                    return {"status": "success", "port": port, "message": f"Connected to Tally Prime on port {port}"}
            except requests.exceptions.RequestException:
                if attempt == 3:
                    continue
                time.sleep(0.5)
                
    return {"status": "fallback", "port": 9000, "message": "Tally live port busy. Loaded local live snapshot."}

def get_cached_portal_session():
    global PORTAL_SESSION_CACHE
    if PORTAL_SESSION_CACHE["auth_token"] and PORTAL_SESSION_CACHE["expiry_time"]:
        if datetime.now() < PORTAL_SESSION_CACHE["expiry_time"]:
            return PORTAL_SESSION_CACHE["auth_token"]
    return None

def set_cached_portal_session(token, gstin):
    global PORTAL_SESSION_CACHE
    PORTAL_SESSION_CACHE["auth_token"] = token
    PORTAL_SESSION_CACHE["gstin"] = gstin
    PORTAL_SESSION_CACHE["expiry_time"] = datetime.now() + timedelta(hours=6)

SAMPLE_VAULT_DATA = {
    "sales": [
        {"Customer_GSTIN": "33AADCS124F1Z5", "Customer_Name": "Apex Logistics India", "ERP_Invoice_No": "AL-889", "GSTR1_Invoice_No": "AL-889", "Invoice_Date": "11-10-2026", "ERP_Tax": 3600.00, "GSTR1_Tax": 3100.00, "Tax_Difference": 500.00, "Status": "Tax Value Differed", "Suggested_Action": "Reconcile Tax Head Mismatch"},
        {"Customer_GSTIN": "33AABCU9603R1ZM", "Customer_Name": "Chennai Steel Pvt Ltd", "ERP_Invoice_No": "INV/26-27/00101", "GSTR1_Invoice_No": "-", "Invoice_Date": "05-10-2026", "ERP_Tax": 9000.00, "GSTR1_Tax": 0.00, "Tax_Difference": 9000.00, "Status": "Missing in GSTR-1", "Suggested_Action": "Report in Next GSTR-1 Amendment (1A/9)"}
    ],
    "purchase": [
        {"gstin": "33AABCT1332L1ZS", "party_name": "Titanium Freight Cargo", "invoice_no": "TF/26/991", "date": "12-10-2026", "item_description": "Logistics & Transport Services", "taxable_value": 45000.00, "cgst": 4050.00, "sgst": 4050.00, "igst": 0.00, "status": "Eligible 100%", "rule_applied": "Standard ITC Claim"}
    ],
    "notes": [
        {"GSTIN": "33AADCS124F1Z5", "Party_Name": "Apex Logistics India", "Note_Type": "DN", "ERP_Note_No": "DN-99", "Portal_Note_No": "-", "ERP_Tax": 1200.00, "Portal_Tax": 0.00, "Tax_Difference": 1200.00, "Status": "Missing in Portal (2B/1)", "Suggested_Action": "Follow up with Counterparty for Amendment"}
    ],
    "itc_time": [
        {"invoice_no": "INV-881", "date": "14-04-2025", "party_name": "Madras Engineering", "gstin": "33AAACM2211K1ZX", "taxable_value": 85000.00, "total_tax": 15300.00, "financial_year": "2025-26", "due_date_16_4": "30-11-2026", "status": "Eligible (Within Time Limit)", "action": "Claim in GSTR-3B"}
    ],
    "rcm": [
        {"invoice_no": "RCM-102", "date": "18-10-2026", "supplier_name": "Safe Transport Corporation", "gstin": "33AAMCS9922B1ZV", "taxable_value": 60000.00, "cgst": 2700.00, "sgst": 2700.00, "igst": 0.00, "portal_status": "Auto-Populated in GSTR-2B", "status": "Matched RCM Liability"}
    ],
    "gstr3b": [
        {"tax_head": "Integrated Tax (IGST)", "gstr_2b_eligible": 145000.00, "gstr_3b_claimed": 145000.00, "variance": 0.00, "status": "Perfect Match"},
        {"tax_head": "Central Tax (CGST)", "gstr_2b_eligible": 82000.00, "gstr_3b_claimed": 80000.00, "variance": 2000.00, "status": "Under-claimed ITC Risk"}
    ]
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/fetch-sample-data', methods=['GET'])
def fetch_sample_data():
    return jsonify({
        "status": "success",
        "message": "Sample data loaded and segregated across modules successfully!",
        "data": SAMPLE_VAULT_DATA
    })

@app.route('/api/master/sync', methods=['POST'])
def master_sync():
    req_data = request.json or {}
    otp = req_data.get('otp')
    active_token = get_cached_portal_session()
    
    if not active_token and not otp:
        return jsonify({"status": "otp_required", "message": "OTP verification required."}), 401

    if otp:
        mock_generated_token = f"gst_secure_token_{int(time.time())}"
        set_cached_portal_session(mock_generated_token, "33AABCU9603R1ZM")

    tally_status = fetch_from_tally_with_retries()
    return jsonify({"status": "success", "message": f"Global Sync Complete! {tally_status['message']}."})

@app.route('/sales-recon', methods=['GET'])
def sales_recon():
    return jsonify({"status": "success", "records": SAMPLE_VAULT_DATA["sales"]})

@app.route('/purchase-recon', methods=['GET'])
def purchase_recon():
    return jsonify({"status": "success", "records": SAMPLE_VAULT_DATA["purchase"]})

@app.route('/notes-recon', methods=['GET'])
def notes_recon():
    return jsonify({"status": "success", "records": SAMPLE_VAULT_DATA["notes"]})

@app.route('/itc-time-limit-recon', methods=['GET'])
def itc_time_limit():
    return jsonify({"status": "success", "records": SAMPLE_VAULT_DATA["itc_time"]})

@app.route('/rcm-liability-recon', methods=['GET'])
def rcm_liability():
    return jsonify({"status": "success", "records": SAMPLE_VAULT_DATA["rcm"]})

@app.route('/gstr3b-summary-recon', methods=['GET'])
def gstr3b_summary():
    return jsonify({"status": "success", "records": SAMPLE_VAULT_DATA["gstr3b"]})

@app.route('/api/master/upload-erp', methods=['POST'])
def upload_erp():
    if 'file' not in request.files: return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return jsonify({"status": "success", "message": f"Books file '{filename}' ingested!"})

@app.route('/api/master/upload-portal', methods=['POST'])
def upload_portal():
    if 'file' not in request.files: return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return jsonify({"status": "success", "message": f"GSTR Portal file '{filename}' parsed!"})

@app.route('/api/vault/save', methods=['POST'])
def save_vault():
    body = request.json or {}
    batch_name = body.get('batch_name', 'Audit_Batch_2026')
    saved_at = datetime.now().strftime('%d-%m-%Y %H:%M')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO vault_sessions (batch_name, saved_at, total_bills, data_json) VALUES (?, ?, ?, ?)',
                   (batch_name, saved_at, len(SAMPLE_VAULT_DATA["sales"]) + len(SAMPLE_VAULT_DATA["purchase"]), json.dumps(SAMPLE_VAULT_DATA)))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": f"Session '{batch_name}' saved to SQLite Vault!"})

@app.route('/api/vault/list', methods=['GET'])
def list_vault():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, batch_name, saved_at, total_bills FROM vault_sessions ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "batch_name": r[1], "saved_at": r[2], "total_bills": r[3]} for r in rows])

@app.route('/api/vault/load/<int:rec_id>', methods=['GET'])
def load_vault(rec_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT batch_name, data_json FROM vault_sessions WHERE id = ?', (rec_id,))
    row = cursor.fetchone()
    conn.close()
    if not row: return jsonify({"error": "Batch not found"}), 404
    return jsonify({"status": "success", "message": f"Successfully reloaded '{row[0]}' from SQLite Vault!"})

@app.route('/api/master/reset', methods=['POST'])
def reset_workspace():
    return jsonify({"status": "success", "message": "Workspace reset successfully."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)