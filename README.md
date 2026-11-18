# CA GST Suite Pro — Professional Tax Workstation & Reconciliation Engine

An enterprise-grade, multi-modular GST reconciliation workstation built specifically for Chartered Accountants and tax professionals. Designed to bridge internal ERP records (Tally Prime / ERPNext) with official GST portal return filings (GSTR-1, GSTR-2B, GSTR-3B) with advanced automated matching algorithms and SQLite session persistence.

---

## 🚀 Key Features & Modules

1. **Master Ingestion & Global Sync Hub (Home):**
   - Live API connectors for Tally Prime (local port scanning from `9000` to `9015`) and GST Portal 2FA authentication flow with OTP verification.
   - Dual Ingestion Gateway: Support for bulk upload of ERP books and official GSTR portal return dumps (`.xlsx`, `.csv`, `.json`, `.xml`).
   - One-click **"Fetch Sample Data"** demo button to instantly populate pre-configured test datasets across all modules.

2. **Module 1: Sales Reconciliation vs GSTR-1**
   - Cross-matches Tally sales registers against GSTR-1 filings.
   - Detects tax value differences, missing invoices in portal, and missing entries in books with adjustable tax variance tolerances (±₹).

3. **Module 2: Purchase Reconciliation & ITC u/s 17(5)**
   - Validates input tax credit claims against GSTR-2B.
   - Implements strict Section 17(5) blocking rules and eligibility flags.

4. **Module 3: Credit / Debit Notes Reconciliation (Mod 3)**
   - Reconciles commercial and financial credit/debit notes between books and portal returns.
   - Filters dynamically by Note Type (CN/DN).

5. **Module 4: ITC 16(4) Time-Limit Validation Engine (Mod 4)**
   - Tracks statutory time limits and due dates (e.g., 30th November of the succeeding financial year) for eligible input tax credit claims.

6. **Module 5: RCM Liability Matcher (Mod 5)**
   - Matches reverse charge mechanism tax liabilities and portal auto-populations.

7. **Module 6: GSTR-3B vs 2B Summary Dashboard (Mod 6)**
   - Compares GSTR-3B tax heads against GSTR-2B eligible ITC to catch under-claimed variances and compliance risks.

8. **SQLite Reconciliation Vault:**
   - Save audit sessions into a local SQLite database (`recon_vault.db`) with custom batch naming and reload history anytime.

---

## 🛠️ Technologies Used

- **Backend:** Python, Flask, Pandas, Openpyxl, Requests, Werkzeug
- **Frontend:** HTML5, Tailwind CSS (via CDN), Vanilla JavaScript (Modular view controller, custom dropdowns, real-time search & sorting)
- **Database:** SQLite3 (Session persistence and audit history vault)
- **Packaging:** PyInstaller (for standalone `.exe` generation)

---

## 📦 Installation & Setup Guide

### Prerequisites
- Python 3.8 or higher installed on your system.
- Git (optional, for cloning).

### Step 1: Clone or Open Project Directory
Open your terminal inside the project root folder (`GST RECON`).

### Step 2: Create and Activate Virtual Environment
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies
Install all required Python packages using the requirements file:
```bash
pip install -r requirements.txt
```

### Step 4: Run the Application
Start the Flask development server:
```bash
python main.py
```
Open your web browser and navigate to:
```text
http://127.0.0.1:8000
```

---

## 💻 How to Use

1. **Quick Test (Demo Mode):**
   - Go to the **Home** tab.
   - Scroll down to the File Upload block and click **"Fetch Sample Data & Segregate Across Modules"**.
   - Navigate through Modules 1 to 6 on the sidebar to view pre-loaded reconciliation results, summary cards, and exception filters.

2. **Live Data Ingestion:**
   - Enter your Tally ODBC endpoint (default `http://localhost:9000`) or GSTIN credentials.
   - Alternatively, upload your official ERP books register or GSTR portal return JSON/Excel files using the Upload Gateway.

3. **Vault & Export:**
   - Click **Save** to store your current reconciliation batch into the SQLite Vault.
   - Access saved batches anytime via the **Vault** modal.
   - Click **Export Report** to download formatted reports.

---

## 📦 Packaging as a Standalone Executable (`.exe`)
To package the app into a standalone desktop executable for offline deployment:
```bash
pyinstaller --noconsole --onedir main.py
```
The final standalone bundle will be generated inside the `dist/main/` folder.
