"""
Seed data generator for G&C Deal and Brokerage Automation Platform.
Seeds users, parties, products, and populates the mandatory acceptance worked example.
"""

import os
import sqlite3
from datetime import datetime
from app.core.database import get_db_connection, init_db, log_audit, DB_PATH
from app.core.calculations import (
    convert_quintals_to_tonnes,
    calculate_price_difference,
    calculate_brokerage,
    calculate_taxable_and_gst,
    to_decimal
)

def seed_all(db_path: str = DB_PATH, reset: bool = False):
    if reset and os.path.exists(db_path):
        os.remove(db_path)

    init_db(db_path)
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    # Check if already seeded
    cur.execute("SELECT COUNT(*) FROM parties")
    if cur.fetchone()[0] > 0:
        conn.close()
        return

    now_iso = datetime.now().isoformat()

    # 1. Seed Users
    users = [
        ('USR-001', 'admin', 'Dhruv Aggarwal (Admin)', 'ADMIN', 1, now_iso),
        ('USR-002', 'broker', 'Girish Chander (Broker)', 'BROKER', 1, now_iso),
        ('USR-003', 'accounts', 'Sunil Sharma (Accounts)', 'ACCOUNTS', 1, now_iso),
        ('USR-004', 'viewer', 'Audit Officer (Viewer)', 'VIEWER', 1, now_iso),
    ]
    cur.executemany("INSERT INTO users (id, username, full_name, role, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?)", users)

    # 2. Seed Products
    products = [
        ('PRD-001', 'M.OIL', 'MOIL', 'QUINTAL', 0.1, 5.0, '151491', 'BSY-ITM-001', 1, now_iso),
        ('PRD-002', 'SOYA.OIL', 'SOYA', 'QUINTAL', 0.1, 5.0, '150790', 'BSY-ITM-002', 1, now_iso),
        ('PRD-003', 'PALM.OIL', 'PALM', 'QUINTAL', 0.1, 5.0, '151190', 'BSY-ITM-003', 1, now_iso),
        ('PRD-004', 'GROUNDNUT.OIL', 'GNOT', 'QUINTAL', 0.1, 5.0, '150890', 'BSY-ITM-004', 1, now_iso),
        ('PRD-005', 'SUNFLOWER.OIL', 'SUNF', 'QUINTAL', 0.1, 5.0, '151219', 'BSY-ITM-005', 1, now_iso),
    ]
    cur.executemany("INSERT INTO products (id, name, short_code, default_unit, quintal_to_tonne_ratio, default_gst_rate, hsn_sac_code, busy_item_id, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", products)

    # 3. Seed Parties
    parties = [
        ('PTY-001', 'HARYANA INDUSTRIES, PANCHKULA', 'haryana industries panchkula', 'BOTH', 'Plot 45, Industrial Area Phase 1', 'Panchkula', 'Haryana', 'Rajesh Gupta', '+91 98120 45678', 'haryana.ind@example.com', '06AAACH2234M1Z2', 50.0, 50.0, 1, 500000.0, 'Primary trading client', 'BSY-LED-001', 1, now_iso, now_iso),
        ('PTY-002', 'NAGPAL ENTERPRISES PVT. LTD., ANOUPGARH', 'nagpal enterprises pvt ltd anoupgarh', 'SELLER', 'Mandi Yard, Sector 3', 'Anoupgarh', 'Rajasthan', 'Vikram Nagpal', '+91 94140 12345', 'nagpal.ent@example.com', '08AABCN9876Q1Z4', 50.0, 50.0, 1, 1000000.0, 'Major mustard oil crusher', 'BSY-LED-002', 1, now_iso, now_iso),
        ('PTY-003', 'M.L. NAGPAL INDUSTRIES, ANOUPGARH', 'ml nagpal industries anoupgarh', 'BOTH', 'Near Railway Siding', 'Anoupgarh', 'Rajasthan', 'Mohan Lal Nagpal', '+91 98290 67890', 'mlnagpal@example.com', '08AACCM4567P1Z8', 50.0, 50.0, 1, 800000.0, 'Intermediate processor & trader', 'BSY-LED-003', 1, now_iso, now_iso),
        ('PTY-004', 'SHAKTI NUTRITIONS PVT. LTD.', 'shakti nutritions pvt ltd', 'BUYER', 'NH-8, Packaging Zone', 'Rewari', 'Haryana', 'Amit Sharma', '+91 98765 43210', 'shakti.nutritions@example.com', '06AABCS1122K1Z9', 50.0, 50.0, 1, 1200000.0, 'Institutional packing & distribution', 'BSY-LED-004', 1, now_iso, now_iso),
        ('PTY-005', 'RAJASTHAN OIL MILLS, SRI GANGANAGAR', 'rajasthan oil mills sri ganganagar', 'SELLER', 'Grain Market Complex', 'Sri Ganganagar', 'Rajasthan', 'Suresh Bansal', '+91 94142 88990', 'raj.oil@example.com', '08AAACR5544N1Z1', 40.0, 40.0, 1, 750000.0, 'Regular supplier', 'BSY-LED-005', 1, now_iso, now_iso),
        ('PTY-006', 'KUBER EDIBLES, HISAR', 'kuber edibles hisar', 'BUYER', 'Barwala Road', 'Hisar', 'Haryana', 'Praveen Jindal', '+91 99912 33445', 'kuber.hisar@example.com', '06AAACK8877L1Z6', 50.0, 50.0, 1, 600000.0, 'Wholesale consumer', 'BSY-LED-006', 1, now_iso, now_iso),
        ('PTY-007', 'SHREE GANESH AGRO TRADERS, ALWAR', 'shree ganesh agro traders alwar', 'BOTH', 'Old Subzi Mandi', 'Alwar', 'Rajasthan', 'Ganesh Kumar', '+91 94141 55667', 'ganesh.agro@example.com', '08AABCS9988H1Z3', 45.0, 45.0, 1, 400000.0, 'Regional distributor', 'BSY-LED-007', 1, now_iso, now_iso),
    ]
    cur.executemany("""
        INSERT INTO parties (
            id, legal_name, normalized_name, party_type, address, city, state,
            contact_person, phone, email, gstin, default_buyer_brokerage_per_tonne,
            default_seller_brokerage_per_tonne, brokerage_enabled, credit_limit, notes,
            busy_ledger_id, is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, parties)

    # 4. Seed Mandatory Acceptance Worked Example (Lot LOT-2026-001)
    chain_id = "LOT-2026-001"
    cur.execute("""
        INSERT INTO deal_chains (id, initial_deal_id, product_id, initial_quantity_qtl, remaining_unresold_quantity_qtl, original_bill_seller_id, final_bill_buyer_id, final_billing_rate_qtl, final_gst_treatment, status, approval_status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        chain_id, "DL-2026-0001", "PRD-001", 320.0, 0.0,
        "PTY-002", # NAGPAL ENTERPRISES PVT. LTD.
        "PTY-004", # SHAKTI NUTRITIONS PVT. LTD.
        16700.0, "PLUS_GST", "READY_FOR_BILLING", "APPROVED", "2026-07-01T10:00:00", "2026-08-11T14:30:00"
    ))

    # Deal 1: 01/07/2026 - Haryana Industries purchases from Nagpal Enterprises
    # 320 Quintals (32 Tonnes) @ 15,700 + GST
    d1_calc_tax = calculate_taxable_and_gst(320, 15700, True, 5.0)
    d1_calc_brok = calculate_brokerage(32, 50, 50)
    cur.execute("""
        INSERT INTO deals (
            id, chain_id, link_sequence, parent_deal_id, deal_date, seller_id, buyer_id, product_id,
            quantity_qtl, quantity_tonnes, rate_per_qtl, authorized_selling_rate_qtl,
            gst_applicable, gst_percentage, is_rate_inclusive_gst, delivery_date,
            buyer_brokerage_rate_per_tonne, seller_brokerage_rate_per_tonne,
            buyer_brokerage_amount, seller_brokerage_amount, total_brokerage_amount,
            price_diff_per_qtl, price_diff_profit, delivery_status, status,
            is_brokerage_overridden, brokerage_override_reason, notes,
            created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "DL-2026-0001", chain_id, 1, None, "2026-07-01", "PTY-002", "PTY-001", "PRD-001",
        320.0, 32.0, 15700.0, 0.0,
        1, 5.0, 0, "2026-07-31",
        50.0, 50.0,
        float(d1_calc_brok['buyer_brokerage']), float(d1_calc_brok['seller_brokerage']), float(d1_calc_brok['total_brokerage']),
        0.0, 0.0, "DELIVERED", "CONFIRMED",
        0, "", "Initial bulk contract 320 quintals (32 tonnes)",
        "USR-002", "2026-07-01T10:00:00", "2026-07-01T10:00:00"
    ))

    # Link 1 (Deal 2): 18/07/2026 - Haryana Industries instructs resale @ 16,450. Sold to M.L. Nagpal @ 16,475 + GST
    # Price Diff: 16,475 - 16,450 = 25/qtl. Profit: 25 * 320 = ₹8,000
    d2_diff = calculate_price_difference(16475, 16450, 320)
    d2_brok = calculate_brokerage(32, 50, 50)
    cur.execute("""
        INSERT INTO deals (
            id, chain_id, link_sequence, parent_deal_id, deal_date, seller_id, buyer_id, product_id,
            quantity_qtl, quantity_tonnes, rate_per_qtl, authorized_selling_rate_qtl,
            gst_applicable, gst_percentage, is_rate_inclusive_gst, delivery_date,
            buyer_brokerage_rate_per_tonne, seller_brokerage_rate_per_tonne,
            buyer_brokerage_amount, seller_brokerage_amount, total_brokerage_amount,
            price_diff_per_qtl, price_diff_profit, delivery_status, status,
            is_brokerage_overridden, brokerage_override_reason, notes,
            created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "DL-2026-0002", chain_id, 2, "DL-2026-0001", "2026-07-18", "PTY-001", "PTY-003", "PRD-001",
        320.0, 32.0, 16475.0, 16450.0,
        1, 5.0, 0, "2026-07-31",
        50.0, 50.0,
        float(d2_brok['buyer_brokerage']), float(d2_brok['seller_brokerage']), float(d2_brok['total_brokerage']),
        float(d2_diff['price_diff_per_qtl']), float(d2_diff['price_diff_profit']), "DELIVERED", "CONFIRMED",
        0, "", "Resale instructed by Haryana Ind @ 16450/qtl, executed @ 16475/qtl",
        "USR-002", "2026-07-18T11:30:00", "2026-07-18T11:30:00"
    ))

    # Link 2 (Deal 3): 30/07/2026 -> 11/08/2026 - M.L. Nagpal instructs @ 16,475. Sold to Shakti Nutritions @ 16,700 + GST
    # Price Diff: 16,700 - 16,475 = 225/qtl. Profit: 225 * 320 = ₹72,000
    d3_diff = calculate_price_difference(16700, 16475, 320)
    d3_brok = calculate_brokerage(32, 50, 50)
    cur.execute("""
        INSERT INTO deals (
            id, chain_id, link_sequence, parent_deal_id, deal_date, seller_id, buyer_id, product_id,
            quantity_qtl, quantity_tonnes, rate_per_qtl, authorized_selling_rate_qtl,
            gst_applicable, gst_percentage, is_rate_inclusive_gst, delivery_date,
            buyer_brokerage_rate_per_tonne, seller_brokerage_rate_per_tonne,
            buyer_brokerage_amount, seller_brokerage_amount, total_brokerage_amount,
            price_diff_per_qtl, price_diff_profit, delivery_status, status,
            is_brokerage_overridden, brokerage_override_reason, notes,
            created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "DL-2026-0003", chain_id, 3, "DL-2026-0002", "2026-07-30", "PTY-003", "PTY-004", "PRD-001",
        320.0, 32.0, 16700.0, 16475.0,
        1, 5.0, 0, "2026-08-11",
        50.0, 50.0,
        float(d3_brok['buyer_brokerage']), float(d3_brok['seller_brokerage']), float(d3_brok['total_brokerage']),
        float(d3_diff['price_diff_per_qtl']), float(d3_diff['price_diff_profit']), "DELIVERED", "CONFIRMED",
        0, "", "Final resale instructed by M.L. Nagpal @ 16475/qtl, executed to Shakti Nutritions @ 16700/qtl",
        "USR-002", "2026-07-30T16:00:00", "2026-08-11T14:30:00"
    ))

    # Official Direct Billing Instruction for LOT-2026-001
    d3_tax = calculate_taxable_and_gst(320, 16700, True, 5.0)
    cur.execute("""
        INSERT INTO billing_instructions (
            id, chain_id, original_seller_id, final_buyer_id, product_id,
            quantity_qtl, rate_per_qtl, gst_applicable, gst_percentage,
            taxable_value, gst_amount, total_value, delivery_date,
            instruction_text, approval_status, approved_by, approved_at, remarks,
            export_status, export_timestamp, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "BI-2026-0001", chain_id, "PTY-002", "PTY-004", "PRD-001",
        320.0, 16700.0, 1, 5.0,
        float(d3_tax['taxable_value']), float(d3_tax['gst_amount']), float(d3_tax['total_value']), "2026-08-11",
        "NAGPAL ENTERPRISES PVT. LTD., ANOUPGARH will issue a direct bill to SHAKTI NUTRITIONS PVT. LTD. for 320 quintals of M.OIL at ₹16,700.00 + GST per quintal.",
        "APPROVED", "USR-001", "2026-08-12T10:00:00", "Confirmed by Accounts and both parties",
        "UNEXPORTED", None, "2026-08-11T14:30:00"
    ))

    # Seed Brokerage Ledgers for the deals
    ledger_entries = [
        ('LED-001', 'PTY-001', 'DL-2026-0001', chain_id, 'BROKERAGE_DUE_BUYER', 1600.0, 'DL-2026-0001', '2026-07-01', 'Brokerage on purchase of 32 MT M.OIL', 'USR-002', now_iso),
        ('LED-002', 'PTY-002', 'DL-2026-0001', chain_id, 'BROKERAGE_DUE_SELLER', 1600.0, 'DL-2026-0001', '2026-07-01', 'Brokerage on sale of 32 MT M.OIL', 'USR-002', now_iso),
        ('LED-003', 'PTY-003', 'DL-2026-0002', chain_id, 'BROKERAGE_DUE_BUYER', 1600.0, 'DL-2026-0002', '2026-07-18', 'Brokerage on purchase of 32 MT M.OIL', 'USR-002', now_iso),
        ('LED-004', 'PTY-001', 'DL-2026-0002', chain_id, 'BROKERAGE_DUE_SELLER', 1600.0, 'DL-2026-0002', '2026-07-18', 'Brokerage on resale of 32 MT M.OIL', 'USR-002', now_iso),
        ('LED-005', 'PTY-004', 'DL-2026-0003', chain_id, 'BROKERAGE_DUE_BUYER', 1600.0, 'DL-2026-0003', '2026-07-30', 'Brokerage on purchase of 32 MT M.OIL', 'USR-002', now_iso),
        ('LED-006', 'PTY-003', 'DL-2026-0003', chain_id, 'BROKERAGE_DUE_SELLER', 1600.0, 'DL-2026-0003', '2026-07-30', 'Brokerage on resale of 32 MT M.OIL', 'USR-002', now_iso),
        ('LED-007', 'PTY-001', None, None, 'PAYMENT_RECEIVED', -3200.0, 'NEFT-883921', '2026-07-25', 'Brokerage received via NEFT', 'USR-003', now_iso),
    ]
    cur.executemany("INSERT INTO brokerage_ledger (id, party_id, deal_id, chain_id, entry_type, amount, reference_no, entry_date, notes, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ledger_entries)

    # 5. Seed Additional Standalone Deal (Lot LOT-2026-002)
    cur.execute("""
        INSERT INTO deal_chains (id, initial_deal_id, product_id, initial_quantity_qtl, remaining_unresold_quantity_qtl, original_bill_seller_id, final_bill_buyer_id, final_billing_rate_qtl, final_gst_treatment, status, approval_status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "LOT-2026-002", "DL-2026-0004", "PRD-002", 200.0, 200.0,
        "PTY-005", "PTY-006", 14200.0, "PLUS_GST", "OPEN", "PENDING", "2026-08-18T09:00:00", "2026-08-18T09:00:00"
    ))

    d4_brok = calculate_brokerage(20, 40, 40)
    cur.execute("""
        INSERT INTO deals (
            id, chain_id, link_sequence, parent_deal_id, deal_date, seller_id, buyer_id, product_id,
            quantity_qtl, quantity_tonnes, rate_per_qtl, authorized_selling_rate_qtl,
            gst_applicable, gst_percentage, is_rate_inclusive_gst, delivery_date,
            buyer_brokerage_rate_per_tonne, seller_brokerage_rate_per_tonne,
            buyer_brokerage_amount, seller_brokerage_amount, total_brokerage_amount,
            price_diff_per_qtl, price_diff_profit, delivery_status, status,
            is_brokerage_overridden, brokerage_override_reason, notes,
            created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "DL-2026-0004", "LOT-2026-002", 1, None, "2026-08-18", "PTY-005", "PTY-006", "PRD-002",
        200.0, 20.0, 14200.0, 0.0,
        1, 5.0, 0, "2026-08-25",
        40.0, 40.0,
        float(d4_brok['buyer_brokerage']), float(d4_brok['seller_brokerage']), float(d4_brok['total_brokerage']),
        0.0, 0.0, "PENDING", "CONFIRMED",
        0, "", "Spot contract for 200 Quintals Soya Oil",
        "USR-002", "2026-08-18T09:00:00", "2026-08-18T09:00:00"
    ))

    # Audit Logs
    log_audit(conn, "deal_chains", "LOT-2026-001", "CREATE", "Dhruv Aggarwal", "ADMIN", None, {"chain_id": "LOT-2026-001", "initial_qty": 320}, "Initial System Seed")
    log_audit(conn, "deals", "DL-2026-0001", "CREATE", "Girish Chander", "BROKER", None, {"deal_id": "DL-2026-0001", "rate": 15700}, "Initial Deal Creation")
    log_audit(conn, "deals", "DL-2026-0002", "CREATE", "Girish Chander", "BROKER", None, {"deal_id": "DL-2026-0002", "diff_profit": 8000}, "Resale Link 1")
    log_audit(conn, "deals", "DL-2026-0003", "CREATE", "Girish Chander", "BROKER", None, {"deal_id": "DL-2026-0003", "diff_profit": 72000}, "Resale Link 2")
    log_audit(conn, "billing_instructions", "BI-2026-0001", "APPROVE", "Sunil Sharma", "ACCOUNTS", None, {"status": "APPROVED"}, "Billing Instruction Approved")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    seed_all(reset=True)
    print("Database seeded successfully with master records and worked example!")
