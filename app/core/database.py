"""
Database management module for G&C Deal and Brokerage Automation Platform.
Embedded SQLite with normalized schema, foreign key constraints, and transactional safety.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "brokerage.db")

def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: str = DB_PATH):
    """Initializes normalized database tables and indexes."""
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
        normalized_name TEXT NOT NULL,
        party_type TEXT NOT NULL CHECK(party_type IN ('BUYER', 'SELLER', 'BOTH')),
        address TEXT,
        city TEXT,
        state TEXT,
        contact_person TEXT,
        phone TEXT,
        email TEXT,
        gstin TEXT,
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

    -- Deals (Individual Purchase & Resale Transactions)
    CREATE TABLE IF NOT EXISTS deals (
        id TEXT PRIMARY KEY,
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
        authorized_selling_rate_qtl REAL DEFAULT 0.0,
        gst_applicable INTEGER DEFAULT 1,
        gst_percentage REAL DEFAULT 5.0,
        is_rate_inclusive_gst INTEGER DEFAULT 0,
        delivery_date TEXT NOT NULL,
        buyer_brokerage_rate_per_tonne REAL DEFAULT 0.0,
        seller_brokerage_rate_per_tonne REAL DEFAULT 0.0,
        buyer_brokerage_amount REAL DEFAULT 0.0,
        seller_brokerage_amount REAL DEFAULT 0.0,
        total_brokerage_amount REAL DEFAULT 0.0,
        price_diff_per_qtl REAL DEFAULT 0.0,
        price_diff_profit REAL DEFAULT 0.0,
        delivery_status TEXT DEFAULT 'PENDING' CHECK(delivery_status IN ('PENDING', 'DELIVERED', 'OVERDUE')),
        status TEXT DEFAULT 'CONFIRMED' CHECK(status IN ('DRAFT', 'CONFIRMED', 'COMPLETED', 'CANCELLED')),
        is_brokerage_overridden INTEGER DEFAULT 0,
        brokerage_override_reason TEXT,
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (chain_id) REFERENCES deal_chains(id),
        FOREIGN KEY (parent_deal_id) REFERENCES deals(id),
        FOREIGN KEY (seller_id) REFERENCES parties(id),
        FOREIGN KEY (buyer_id) REFERENCES parties(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
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
