"""
Database management module for G&C Deal and Brokerage Automation Platform.
Embedded SQLite with normalized schema, foreign key constraints, and transactional safety.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_PATH = os.environ.get("DATABASE_PATH") or os.environ.get("DB_PATH") or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "brokerage.db")

def get_db_connection(db_path: str = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: str = None):
    """Initializes normalized database tables, migrations, and indexes."""
    if db_path is None:
        db_path = DB_PATH
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.executescript("""
    -- Users and Roles
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('ADMIN', 'BROKER', 'ACCOUNTS', 'VIEWER')),
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );

    -- Party Master
    CREATE TABLE IF NOT EXISTS parties (
        id TEXT PRIMARY KEY,
        legal_name TEXT UNIQUE NOT NULL,
        trade_name TEXT,
        normalized_name TEXT NOT NULL,
        party_type TEXT NOT NULL CHECK(party_type IN ('BUYER', 'SELLER', 'BOTH')),
        mandi_station TEXT,
        address TEXT,
        city TEXT,
        state TEXT,
        contact_person TEXT,
        phone TEXT,
        email TEXT,
        gstin TEXT,
        pan TEXT,
        bank_name TEXT,
        bank_account_no TEXT,
        bank_ifsc TEXT,
        bank_branch TEXT,
        contacts_json TEXT, -- JSON array of [{name, role, phone, email}]
        default_buyer_brokerage_per_tonne REAL DEFAULT 0.0,
        default_seller_brokerage_per_tonne REAL DEFAULT 0.0,
        brokerage_enabled INTEGER DEFAULT 1,
        credit_limit REAL DEFAULT 0.0,
        notes TEXT,
        busy_ledger_id TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    -- Product Master
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        short_code TEXT NOT NULL,
        default_unit TEXT DEFAULT 'QUINTAL',
        quintal_to_tonne_ratio REAL DEFAULT 0.1,
        default_gst_rate REAL DEFAULT 5.0,
        hsn_sac_code TEXT,
        busy_item_id TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );

    -- Deal Chains (Lots)
    CREATE TABLE IF NOT EXISTS deal_chains (
        id TEXT PRIMARY KEY,
        initial_deal_id TEXT,
        product_id TEXT NOT NULL,
        initial_quantity_qtl REAL NOT NULL,
        remaining_unresold_quantity_qtl REAL NOT NULL,
        original_bill_seller_id TEXT NOT NULL,
        final_bill_buyer_id TEXT,
        final_billing_rate_qtl REAL,
        final_gst_treatment TEXT DEFAULT 'PLUS_GST',
        status TEXT DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'CHAINED', 'READY_FOR_BILLING', 'INVOICED', 'CANCELLED')),
        approval_status TEXT DEFAULT 'PENDING' CHECK(approval_status IN ('PENDING', 'APPROVED', 'REJECTED')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (original_bill_seller_id) REFERENCES parties(id),
        FOREIGN KEY (final_bill_buyer_id) REFERENCES parties(id)
    );

    -- Deals (Individual Purchase & Resale Transactions / Bargains)
    CREATE TABLE IF NOT EXISTS deals (
        id TEXT PRIMARY KEY,
        bgn_code TEXT, -- Display Bargain ID e.g. BGN-006
        chain_id TEXT NOT NULL,
        link_sequence INTEGER DEFAULT 1,
        parent_deal_id TEXT,
        deal_date TEXT NOT NULL,
        seller_id TEXT NOT NULL,
        buyer_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        quantity_qtl REAL NOT NULL,
        quantity_tonnes REAL NOT NULL,
        rate_per_qtl REAL NOT NULL,
        seller_rate REAL DEFAULT 0.0,
        buyer_rate REAL DEFAULT 0.0,
        authorized_selling_rate_qtl REAL DEFAULT 0.0,
        gst_applicable INTEGER DEFAULT 1,
        gst_percentage REAL DEFAULT 5.0,
        is_rate_inclusive_gst INTEGER DEFAULT 0,
        delivery_date TEXT NOT NULL,
        advance_payment_date TEXT,
        delivery_condition TEXT,
        is_buyer_confirmed INTEGER DEFAULT 1,
        is_seller_confirmed INTEGER DEFAULT 1,
        reconfirmation_required INTEGER DEFAULT 0,
        buyer_brokerage_rate_per_tonne REAL DEFAULT 0.0,
        seller_brokerage_rate_per_tonne REAL DEFAULT 0.0,
        buyer_brokerage_amount REAL DEFAULT 0.0,
        seller_brokerage_amount REAL DEFAULT 0.0,
        total_brokerage_amount REAL DEFAULT 0.0,
        price_diff_per_qtl REAL DEFAULT 0.0,
        price_diff_profit REAL DEFAULT 0.0,
        delivery_status TEXT DEFAULT 'PENDING' CHECK(delivery_status IN ('PENDING', 'DELIVERED', 'OVERDUE')),
        status TEXT DEFAULT 'CONFIRMED' CHECK(status IN ('DRAFT', 'PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED', 'UPDATED')),
        is_brokerage_overridden INTEGER DEFAULT 0,
        brokerage_override_reason TEXT,
        notes TEXT,
        is_deleted INTEGER DEFAULT 0,
        deleted_at TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (chain_id) REFERENCES deal_chains(id),
        FOREIGN KEY (parent_deal_id) REFERENCES deals(id),
        FOREIGN KEY (seller_id) REFERENCES parties(id),
        FOREIGN KEY (buyer_id) REFERENCES parties(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );

    -- Communication & Dispatch Logs (WhatsApp / Email)
    CREATE TABLE IF NOT EXISTS dispatch_logs (
        id TEXT PRIMARY KEY,
        deal_id TEXT NOT NULL,
        recipient_type TEXT NOT NULL CHECK(recipient_type IN ('BUYER', 'SELLER', 'BOTH')),
        recipient_name TEXT NOT NULL,
        channel TEXT NOT NULL CHECK(channel IN ('WHATSAPP', 'EMAIL')),
        phone_or_email TEXT,
        message_preview TEXT,
        status TEXT DEFAULT 'SENT' CHECK(status IN ('SENT', 'FAILED', 'PENDING', 'OPENED', 'DELIVERED')),
        sent_by TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (deal_id) REFERENCES deals(id)
    );

    -- Official Direct Billing Instructions
    CREATE TABLE IF NOT EXISTS billing_instructions (
        id TEXT PRIMARY KEY,
        chain_id TEXT UNIQUE NOT NULL,
        original_seller_id TEXT NOT NULL,
        final_buyer_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        quantity_qtl REAL NOT NULL,
        rate_per_qtl REAL NOT NULL,
        gst_applicable INTEGER DEFAULT 1,
        gst_percentage REAL DEFAULT 5.0,
        taxable_value REAL NOT NULL,
        gst_amount REAL NOT NULL,
        total_value REAL NOT NULL,
        delivery_date TEXT NOT NULL,
        instruction_text TEXT NOT NULL,
        approval_status TEXT DEFAULT 'PENDING_REVIEW' CHECK(approval_status IN ('PENDING_REVIEW', 'APPROVED', 'EXPORTED_TO_EXCEL', 'SYNCED_TO_BUSY')),
        approved_by TEXT,
        approved_at TEXT,
        remarks TEXT,
        export_status TEXT DEFAULT 'UNEXPORTED',
        export_timestamp TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (chain_id) REFERENCES deal_chains(id),
        FOREIGN KEY (original_seller_id) REFERENCES parties(id),
        FOREIGN KEY (final_buyer_id) REFERENCES parties(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );

    -- Brokerage & Party Ledger
    CREATE TABLE IF NOT EXISTS brokerage_ledger (
        id TEXT PRIMARY KEY,
        party_id TEXT NOT NULL,
        deal_id TEXT,
        chain_id TEXT,
        entry_type TEXT NOT NULL CHECK(entry_type IN ('BROKERAGE_DUE_BUYER', 'BROKERAGE_DUE_SELLER', 'PAYMENT_RECEIVED', 'ADJUSTMENT', 'DISCOUNT')),
        amount REAL NOT NULL,
        reference_no TEXT,
        entry_date TEXT NOT NULL,
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (party_id) REFERENCES parties(id),
        FOREIGN KEY (deal_id) REFERENCES deals(id)
    );

    -- Audit Logs (Immutable)
    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY,
        entity_name TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        actor_name TEXT NOT NULL,
        actor_role TEXT NOT NULL,
        old_values TEXT,
        new_values TEXT,
        reason TEXT,
        created_at TEXT NOT NULL
    );

    -- Excel Export Logs
    CREATE TABLE IF NOT EXISTS excel_export_logs (
        id TEXT PRIMARY KEY,
        export_key TEXT NOT NULL,
        version INTEGER DEFAULT 1,
        record_count INTEGER NOT NULL,
        sheet_types TEXT,
        exported_by TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    -- BUSY Integration Mappings & Sync Staging
    CREATE TABLE IF NOT EXISTS busy_mappings (
        id TEXT PRIMARY KEY,
        mapping_type TEXT NOT NULL, -- 'PARTY' or 'PRODUCT'
        internal_id TEXT NOT NULL,
        busy_code TEXT NOT NULL,
        busy_name TEXT NOT NULL,
        notes TEXT,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS busy_sync_logs (
        id TEXT PRIMARY KEY,
        voucher_no TEXT NOT NULL,
        chain_id TEXT NOT NULL,
        payload TEXT NOT NULL,
        sync_status TEXT NOT NULL CHECK(sync_status IN ('READY', 'STAGED', 'SYNCED', 'FAILED')),
        error_message TEXT,
        synced_at TEXT NOT NULL
    );

    -- Indexes for high speed querying
    CREATE INDEX IF NOT EXISTS idx_deals_chain_id ON deals(chain_id);
    CREATE INDEX IF NOT EXISTS idx_deals_deal_date ON deals(deal_date);
    CREATE INDEX IF NOT EXISTS idx_deals_seller ON deals(seller_id);
    CREATE INDEX IF NOT EXISTS idx_deals_buyer ON deals(buyer_id);
    CREATE INDEX IF NOT EXISTS idx_ledger_party ON brokerage_ledger(party_id);
    CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_name, entity_id);
    """)

    # Migration checks for existing parties table
    for col in ['trade_name', 'mandi_station', 'pan', 'bank_name', 'bank_account_no', 'bank_ifsc', 'bank_branch']:
        try:
            cur.execute(f"ALTER TABLE parties ADD COLUMN {col} TEXT")
        except Exception:
            pass

    # Migration checks for existing deals table (Dual-Rate: seller_rate & buyer_rate)
    cur.execute("PRAGMA table_info(deals)")
    existing_deal_cols = [r['name'] for r in cur.fetchall()]

    if 'seller_rate' not in existing_deal_cols:
        try:
            cur.execute("ALTER TABLE deals ADD COLUMN seller_rate REAL DEFAULT 0.0")
        except Exception:
            pass
    if 'buyer_rate' not in existing_deal_cols:
        try:
            cur.execute("ALTER TABLE deals ADD COLUMN buyer_rate REAL DEFAULT 0.0")
        except Exception:
            pass
    if 'reconfirmation_required' not in existing_deal_cols:
        try:
            cur.execute("ALTER TABLE deals ADD COLUMN reconfirmation_required INTEGER DEFAULT 0")
        except Exception:
            pass

    # Safe backfill for pre-existing deals: seller_rate & buyer_rate = rate_per_qtl
    try:
        cur.execute("UPDATE deals SET seller_rate = rate_per_qtl WHERE seller_rate IS NULL OR seller_rate = 0.0")
        cur.execute("UPDATE deals SET buyer_rate = rate_per_qtl WHERE buyer_rate IS NULL OR buyer_rate = 0.0")
        cur.execute("UPDATE deals SET reconfirmation_required = 0 WHERE reconfirmation_required IS NULL")
    except Exception:
        pass

    conn.commit()
    conn.close()

def log_audit(
    conn: sqlite3.Connection,
    entity_name: str,
    entity_id: str,
    action: str,
    actor_name: str,
    actor_role: str,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None
):
    """Inserts an immutable audit event record."""
    audit_id = f"AUD-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    old_json = json.dumps(old_values, default=str) if old_values else None
    new_json = json.dumps(new_values, default=str) if new_values else None

    conn.execute("""
        INSERT INTO audit_logs (id, entity_name, entity_id, action, actor_name, actor_role, old_values, new_values, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (audit_id, entity_name, entity_id, action, actor_name, actor_role, old_json, new_json, reason, datetime.now().isoformat()))
