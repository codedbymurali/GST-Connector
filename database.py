import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "recon_vault.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recon_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_name TEXT,
            saved_at TEXT,
            total_bills INTEGER,
            erp_tax REAL,
            portal_tax REAL,
            data_json TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_reconciliation(batch_name: str, df: pd.DataFrame):
    init_db()
    conn = sqlite3.connect(DB_NAME)
    
    total_bills = len(df)
    erp_tax = float(df["ERP_Tax"].sum()) if not df.empty and "ERP_Tax" in df.columns else 0.0
    portal_tax = float(df["Portal_Tax"].sum()) if not df.empty and "Portal_Tax" in df.columns else 0.0
    data_json = df.to_json(orient="records") if not df.empty else "[]"
    saved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO recon_history (batch_name, saved_at, total_bills, erp_tax, portal_tax, data_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (batch_name, saved_at, total_bills, erp_tax, portal_tax, data_json))
    
    conn.commit()
    conn.close()

def get_all_history() -> list:
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, batch_name, saved_at, total_bills, erp_tax, portal_tax FROM recon_history ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        history.append({
            "id": r[0],
            "batch_name": r[1],
            "saved_at": r[2],
            "total_bills": r[3],
            "erp_tax": r[4],
            "portal_tax": r[5]
        })
    return history

def get_reconciliation_by_id(rec_id: int) -> pd.DataFrame:
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT data_json FROM recon_history WHERE id = ?", (rec_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0]:
        return pd.read_json(row[0], orient="records")
    return pd.DataFrame()