import io
import smtplib
from pathlib import Path
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from fastapi import FastAPI, UploadFile, File, Body, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import uvicorn

from config_and_samples import get_sample_erp_df, get_sample_portal_df
from connectors import parse_uploaded_file, fetch_erpnext_invoices
from modules.purchase_register import run_matching_engine, PurchaseRegisterEngine
from database import init_db, save_reconciliation, get_all_history, get_reconciliation_by_id

app = FastAPI(title="CA GST Suite Pro — Professional Tax Workstation")

# Initialize Database on Startup
init_db()

SESSION_STORE = {
    "erp_df": pd.DataFrame(),
    "portal_df": pd.DataFrame(),
    "reconciled_df": pd.DataFrame(),
    "erp_source_label": "Not Connected",
    "portal_source_label": "Not Connected",
    "active_batch_name": "Unsaved Session"
}

def build_state_response():
    erp_df = SESSION_STORE["erp_df"]
    portal_df = SESSION_STORE["portal_df"]
    reco_df = SESSION_STORE["reconciled_df"]

    party_summary = []
    if not reco_df.empty:
        grp = reco_df.groupby(["GSTIN", "Supplier_Name"], as_index=False).agg(
            Total_Bills=("Status", "count"),
            ERP_Tax=("ERP_Tax", "sum"),
            Portal_Tax=("Portal_Tax", "sum"),
            Diff=("Tax_Difference", "sum")
        )
        party_summary = grp.round(2).to_dict(orient="records")

    return {
        "erp_count": len(erp_df),
        "erp_tax": round(float((erp_df["IGST"] + erp_df["CGST"] + erp_df["SGST"]).sum()), 2) if not erp_df.empty else 0,
        "erp_label": SESSION_STORE["erp_source_label"],
        "portal_count": len(portal_df),
        "portal_tax": round(float((portal_df["IGST"] + portal_df["CGST"] + portal_df["SGST"]).sum()), 2) if not portal_df.empty else 0,
        "portal_label": SESSION_STORE["portal_source_label"],
        "active_batch_name": SESSION_STORE["active_batch_name"],
        "rows": reco_df.fillna("").to_dict(orient="records") if not reco_df.empty else [],
        "party_summary": party_summary
    }

@app.post("/api/source/erp/sample")
async def load_erp_sample():
    SESSION_STORE["erp_df"] = get_sample_erp_df()
    SESSION_STORE["erp_source_label"] = "Sample ERPNext Data (6 Bills)"
    if not SESSION_STORE["portal_df"].empty:
        SESSION_STORE["reconciled_df"] = run_matching_engine(SESSION_STORE["erp_df"], SESSION_STORE["portal_df"])
    return build_state_response()

@app.post("/api/source/portal/sample")
async def load_portal_sample():
    SESSION_STORE["portal_df"] = get_sample_portal_df()
    SESSION_STORE["portal_source_label"] = "Sample GSTR-2B Portal Data (6 Bills)"
    if not SESSION_STORE["erp_df"].empty:
        SESSION_STORE["reconciled_df"] = run_matching_engine(SESSION_STORE["erp_df"], SESSION_STORE["portal_df"])
    return build_state_response()

@app.post("/api/source/erp/upload")
async def upload_erp_file(file: UploadFile = File(...)):
    content = await file.read()
    SESSION_STORE["erp_df"] = parse_uploaded_file(content, file.filename)
    SESSION_STORE["erp_source_label"] = f"Uploaded: {file.filename}"
    if not SESSION_STORE["portal_df"].empty:
        SESSION_STORE["reconciled_df"] = run_matching_engine(SESSION_STORE["erp_df"], SESSION_STORE["portal_df"])
    return build_state_response()

@app.post("/api/source/portal/upload")
async def upload_portal_file(file: UploadFile = File(...)):
    content = await file.read()
    SESSION_STORE["portal_df"] = parse_uploaded_file(content, file.filename)
    SESSION_STORE["portal_source_label"] = f"Uploaded: {file.filename}"
    if not SESSION_STORE["erp_df"].empty:
        SESSION_STORE["reconciled_df"] = run_matching_engine(SESSION_STORE["erp_df"], SESSION_STORE["portal_df"])
    return build_state_response()

@app.post("/api/reconcile-now")
async def trigger_reconcile(payload: dict = Body(...)):
    tol = float(payload.get("tolerance", 2.0))
    SESSION_STORE["reconciled_df"] = run_matching_engine(SESSION_STORE["erp_df"], SESSION_STORE["portal_df"], tol)
    return build_state_response()

@app.post("/api/vault/save")
async def save_to_vault(payload: dict = Body(...)):
    try:
        reco_df = SESSION_STORE["reconciled_df"]
        if reco_df.empty:
            return JSONResponse({"error": "No reconciled data found! Please load ERP and Portal samples/files and run reconciliation first."}, status_code=400)
        
        batch_name = payload.get("batch_name", "October_2026_Recon").strip()
        if not batch_name:
            batch_name = "October_2026_Recon"
            
        save_reconciliation(batch_name, reco_df)
        SESSION_STORE["active_batch_name"] = batch_name
        return {"status": "success", "message": f"Successfully saved '{batch_name}' to SQLite Vault!"}
    except Exception as e:
        return JSONResponse({"error": f"Server error while saving: {str(e)}"}, status_code=500)

@app.get("/api/vault/list")
async def list_vault_history():
    try:
        return get_all_history()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/vault/load/{rec_id}")
async def load_from_vault(rec_id: int):
    df = get_reconciliation_by_id(rec_id)
    if df.empty:
        return JSONResponse({"error": "Reconciliation record not found in vault."}, status_code=404)
    SESSION_STORE["reconciled_df"] = df
    SESSION_STORE["active_batch_name"] = f"Loaded_Vault_ID_{rec_id}"
    return build_state_response()

@app.post("/api/vault/email")
async def email_report(payload: dict = Body(...)):
    try:
        reco_df = SESSION_STORE["reconciled_df"]
        if reco_df.empty:
            return JSONResponse({"error": "No reconciliation data available to email."}, status_code=400)
        
        receiver = payload.get("receiver_email", "").strip()
        if not receiver:
            return JSONResponse({"error": "Receiver email is required."}, status_code=400)
        
        sender_email = payload.get("sender_email", "your_email@gmail.com")
        sender_password = payload.get("sender_password", "your_app_password")
        batch_name = SESSION_STORE.get("active_batch_name", "Monthly_Recon")
        
        summary_stats = {
            "total_bills": len(reco_df),
            "erp_tax": float(reco_df["ERP_Tax"].sum()) if "ERP_Tax" in reco_df.columns else 0.0,
            "portal_tax": float(reco_df["Portal_Tax"].sum()) if "Portal_Tax" in reco_df.columns else 0.0
        }

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver
        msg['Subject'] = f"📊 GST Reconciliation Report — {batch_name}"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
                <h2 style="color: #4f46e5; margin-top: 0;">GST Reconciliation Summary</h2>
                <p>Hello,</p>
                <p>Here is the automated reconciliation report for <strong>{batch_name}</strong> generated via CA GST Suite Pro.</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background-color: #f8fafc;">
                        <th style="padding: 10px; border: 1px solid #cbd5e1; text-align: left;">Metric</th>
                        <th style="padding: 10px; border: 1px solid #cbd5e1; text-align: right;">Amount / Count</th>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #cbd5e1;">Total Invoices Processed</td>
                        <td style="padding: 10px; border: 1px solid #cbd5e1; text-align: right;"><strong>{summary_stats['total_bills']}</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #cbd5e1;">Total ERP / Books Tax</td>
                        <td style="padding: 10px; border: 1px solid #cbd5e1; text-align: right; color: #2563eb;"><strong>₹{summary_stats['erp_tax']:,.2f}</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #cbd5e1;">Total Portal 2B Tax</td>
                        <td style="padding: 10px; border: 1px solid #cbd5e1; text-align: right; color: #16a34a;"><strong>₹{summary_stats['portal_tax']:,.2f}</strong></td>
                    </tr>
                </table>
                
                <p style="font-size: 12px; color: #64748b; margin-top: 30px;">Generated automatically by CA GST Suite Pro.</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, 'html'))

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            reco_df.to_excel(writer, sheet_name="Recon_Report", index=False)
        buf.seek(0)

        part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        part.set_payload(buf.getvalue())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="GST_Recon_{batch_name}.xlsx"')
        msg.attach(part)

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver, msg.as_string())
        server.quit()

        return {"status": "success", "message": f"Report successfully emailed to {receiver}!"}
    except Exception as e:
        return JSONResponse({"error": f"Email sending failed: {str(e)}"}, status_code=500)

@app.post("/api/reset")
async def reset_workspace():
    SESSION_STORE["erp_df"] = pd.DataFrame()
    SESSION_STORE["portal_df"] = pd.DataFrame()
    SESSION_STORE["reconciled_df"] = pd.DataFrame()
    SESSION_STORE["erp_source_label"] = "Not Connected"
    SESSION_STORE["portal_source_label"] = "Not Connected"
    SESSION_STORE["active_batch_name"] = "Unsaved Session"
    return build_state_response()

@app.get("/api/export")
async def export_data(status: str = "ALL", fmt: str = "xlsx"):
    df = SESSION_STORE["reconciled_df"]
    if df.empty:
        return JSONResponse({"error": "No reconciled data available to export."}, status_code=400)
    
    if status == "ALL":
        df = df[df["Status"] != "Matched"]
    elif status != "ALL":
        df = df[df["Status"] == status]

    if fmt == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        return StreamingResponse(io.BytesIO(buf.getvalue().encode("utf-8")), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=GST_Recon_{status}.csv"})
    elif fmt == "json":
        return StreamingResponse(io.BytesIO(df.to_json(orient="records", indent=2).encode("utf-8")), media_type="application/json", headers={"Content-Disposition": f"attachment; filename=GST_Recon_{status}.json"})
    else:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Bill_Wise_Recon", index=False)
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=GST_Recon_{status}.xlsx"})

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_path = Path("templates/index.html")
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>Error: templates/index.html file not found!</h1>"

@app.get("/purchase-recon")
async def purchase_reconciliation(request: Request):
    sample_purchases = [
        {
            "invoice_no": "INV-2026-001",
            "date": "2026-11-01",
            "party_name": "ABC Enterprises",
            "gstin": "37AAAAA0000A1Z5",
            "taxable_value": 50000.0,
            "cgst": 4500.0,
            "sgst": 4500.0,
            "igst": 0.0,
            "item_description": "Office laptop accessories",
            "is_rcm": False
        },
        {
            "invoice_no": "INV-2026-002",
            "date": "2026-11-03",
            "party_name": "XYZ Motors",
            "gstin": "37BBBBB1111B1Z6",
            "taxable_value": 100000.0,
            "cgst": 9000.0,
            "sgst": 9000.0,
            "igst": 0.0,
            "item_description": "Car repair and maintenance services",
            "is_rcm": False
        }
    ]
    engine = PurchaseRegisterEngine(sample_purchases)
    processed_data = engine.process_purchase_register()
    summary_metrics = engine.generate_summary(processed_data)
    return {
        "status": "success",
        "module": "Purchase Reconciliation & ITC Eligibility (Module 2)",
        "summary": summary_metrics,
        "records": processed_data
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
