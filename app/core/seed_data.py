"""
Seed data generator for Ganesh & Company Deal and Brokerage Automation Platform.
Seeds authentic Sri Ganganagar mandi parties, contact hierarchy, products, bargains,
live commodity benchmark rates, and dispatch logs.
"""

import os
import json
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

    # Backfill bank details for existing parties if empty or null
    bank_backfills = [
        ('PTY-HARBANS', 'State Bank of India', '38910029381', 'SBIN0031124', 'Sangaria Mandi Branch'),
        ('PTY-TERAI', 'HDFC Bank', '50200088192341', 'HDFC0000456', 'Sevoke Road Commercial Branch'),
        ('PTY-002', 'Punjab National Bank', '0234002100054321', 'PUNB0023400', 'Anoupgarh Mandi Yard'),
        ('PTY-005', 'State Bank of India', '10928374650', 'SBIN0000718', 'Sri Ganganagar Main Branch'),
        ('PTY-001', 'ICICI Bank', '001205019283', 'ICIC0000012', 'Panchkula Sector 9 Branch'),
        ('PTY-004', 'Axis Bank', '918020038471293', 'UTIB0000219', 'Rewari Industrial Area Branch'),
        ('PTY-006', 'Bank of Baroda', '27890200001827', 'BARB0HISARX', 'Hisar Mandi Gate Branch'),
        ('PTY-007', 'Punjab National Bank', '1892002100081234', 'PUNB0189200', 'Alwar Subzi Mandi Branch'),
        ('PTY-003', 'State Bank of India', '31920048172', 'SBIN0031205', 'Anoupgarh Town Branch')
    ]
    for pid, bname, bac, bifsc, bbranch in bank_backfills:
        cur.execute("""
            UPDATE parties
            SET bank_name = ?, bank_account_no = ?, bank_ifsc = ?, bank_branch = ?
            WHERE id = ? AND (bank_name IS NULL OR bank_name = '')
        """, (bname, bac, bifsc, bbranch, pid))
    conn.commit()

    # Check if already seeded with new data
    cur.execute("SELECT COUNT(*) FROM parties WHERE id = 'PTY-HARBANS'")
    if cur.fetchone()[0] > 0 and not reset:
        conn.close()
        return

    now_iso = datetime.now().isoformat()

    # 1. Seed Users
    users = [
        ('USR-001', 'sanjay', 'Sanjay Kumar Aggarwal (Proprietor)', 'ADMIN', 1, now_iso),
        ('USR-002', 'dhruv', 'Dhruv Aggarwal (Manager)', 'BROKER', 1, now_iso),
        ('USR-003', 'accounts', 'Sunil Sharma (Accounts)', 'ACCOUNTS', 1, now_iso),
        ('USR-004', 'viewer', 'Audit Officer (Viewer)', 'VIEWER', 1, now_iso),
    ]
    cur.executemany("INSERT OR REPLACE INTO users (id, username, full_name, role, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?)", users)

    # 2. Seed Products
    products = [
        ('PRD-001', 'M.OIL', 'MOIL', 'QUINTAL', 0.1, 5.0, '151491', 'BSY-ITM-001', 1, now_iso),
        ('PRD-002', 'Mustard Cake (Kachi Ghani)', 'M.CAKE', 'QUINTAL', 0.1, 5.0, '230690', 'BSY-ITM-002', 1, now_iso),
        ('PRD-003', 'Refined Soya Oil', 'SOYA.OIL', 'QUINTAL', 0.1, 5.0, '150790', 'BSY-ITM-003', 1, now_iso),
        ('PRD-004', 'RBD Palm Oil', 'PALM.OIL', 'QUINTAL', 0.1, 5.0, '151190', 'BSY-ITM-004', 1, now_iso),
        ('PRD-005', 'Cottonseed Oil (Wash)', 'COTTON.OIL', 'QUINTAL', 0.1, 5.0, '151229', 'BSY-ITM-005', 1, now_iso),
        ('PRD-006', 'Mustard Oil (Loose)', 'M.OIL.LOOSE', 'QUINTAL', 0.1, 5.0, '151491', 'BSY-ITM-006', 1, now_iso),
    ]
    cur.executemany("INSERT OR REPLACE INTO products (id, name, short_code, default_unit, quintal_to_tonne_ratio, default_gst_rate, hsn_sac_code, busy_item_id, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", products)

    # 3. Seed Parties with Authentic Sri Ganganagar Mandi Details & Contacts Hierarchy
    harbans_contacts = json.dumps([
        {"name": "Kailash Chand Bansal", "role": "Owner", "phone": "+91 94140 51234", "email": "kailash@harbansoil.com"},
        {"name": "Ramesh Kumar", "role": "Dispatch Manager", "phone": "+91 98290 77123", "email": "dispatch@harbansoil.com"},
        {"name": "Pankaj Garg", "role": "Broker / Accounts", "phone": "+91 94601 88234", "email": "accounts@harbansoil.com"}
    ])

    terai_contacts = json.dumps([
        {"name": "Binod Agarwal", "role": "Owner", "phone": "+91 98320 11223", "email": "binod@teraitrading.com"},
        {"name": "Subhash Saha", "role": "Dispatch Manager", "phone": "+91 94340 99881", "email": "logistics@teraitrading.com"},
        {"name": "Amit Sen", "role": "Broker / Accounts", "phone": "+91 98322 44556", "email": "finance@teraitrading.com"}
    ])

    nagpal_contacts = json.dumps([
        {"name": "Vikram Nagpal", "role": "Owner", "phone": "+91 94140 12345", "email": "vikram@nagpalent.com"},
        {"name": "Sanjay Verma", "role": "Dispatch Manager", "phone": "+91 98291 33445", "email": "dispatch@nagpalent.com"}
    ])

    raj_contacts = json.dumps([
        {"name": "Suresh Bansal", "role": "Owner", "phone": "+91 94142 88990", "email": "suresh@rajasthanoil.com"},
        {"name": "Mohan Lal", "role": "Broker / Accounts", "phone": "+91 94619 22334", "email": "accounts@rajasthanoil.com"}
    ])

    haryana_contacts = json.dumps([
        {"name": "Rajesh Gupta", "role": "Owner", "phone": "+91 98120 45678", "email": "rajesh@haryanaind.com"},
        {"name": "Anil Verma", "role": "Dispatch Manager", "phone": "+91 98121 88990", "email": "dispatch@haryanaind.com"}
    ])

    shakti_contacts = json.dumps([
        {"name": "Amit Sharma", "role": "Owner", "phone": "+91 98765 43210", "email": "amit@shaktinutritions.com"},
        {"name": "Rohit Yadav", "role": "Dispatch Manager", "phone": "+91 98760 11223", "email": "factory@shaktinutritions.com"}
    ])

    kuber_contacts = json.dumps([
        {"name": "Praveen Jindal", "role": "Owner", "phone": "+91 99912 33445", "email": "praveen@kuberedibles.com"}
    ])

    alwar_contacts = json.dumps([
        {"name": "Ganesh Kumar", "role": "Owner", "phone": "+91 94141 55667", "email": "ganesh@shreeganeshagro.com"},
        {"name": "Manoj Saini", "role": "Broker / Accounts", "phone": "+91 94143 44556", "email": "accounts@shreeganeshagro.com"}
    ])

    parties = [
        ('PTY-HARBANS', 'HARBANS INDUSTRIES, SANGARIA (RAJASTHAN)', 'Harbans Industries', 'harbans industries sangaria rajasthan', 'SELLER', 'Sangaria, Rajasthan', 'Industrial Area, Mandi Yard', 'Sangaria', 'Rajasthan', 'Kailash Chand Bansal', '+91 94140 51234', 'info@harbansoil.com', '08AAAFH1234K1Z5', 'AAAFH1234K', 'State Bank of India', '38910029381', 'SBIN0031124', 'Sangaria Mandi Branch', harbans_contacts, 50.0, 50.0, 1, 1500000.0, 'Premier mustard oil crushing mill in Sangaria', 'BSY-LED-008', 1, now_iso, now_iso),
        ('PTY-TERAI', 'TERAI ISPAT AND TRADING CO. SILIGURI (WEST BENGAL)', 'Terai Ispat & Trading', 'terai ispat and trading co siliguri west bengal', 'BUYER', 'Siliguri, West Bengal', 'Sevoke Road, Near Mandi Gate', 'Siliguri', 'West Bengal', 'Binod Agarwal', '+91 98320 11223', 'terai.siliguri@example.com', '19AABCT5566L1Z2', 'AABCT5566L', 'HDFC Bank', '50200088192341', 'HDFC0000456', 'Sevoke Road Commercial Branch', terai_contacts, 50.0, 50.0, 1, 2000000.0, 'Major North-East edible oil wholesale distributor', 'BSY-LED-009', 1, now_iso, now_iso),
        ('PTY-002', 'NAGPAL ENTERPRISES PVT. LTD., ANOUPGARH', 'Nagpal Enterprises', 'nagpal enterprises pvt ltd anoupgarh', 'SELLER', 'Anoupgarh, Rajasthan', 'Mandi Yard, Sector 3', 'Anoupgarh', 'Rajasthan', 'Vikram Nagpal', '+91 94140 12345', 'nagpal.ent@example.com', '08AABCN9876Q1Z4', 'AABCN9876Q', 'Punjab National Bank', '0234002100054321', 'PUNB0023400', 'Anoupgarh Mandi Yard', nagpal_contacts, 50.0, 50.0, 1, 1000000.0, 'Major mustard oil crusher in Anoupgarh mandi', 'BSY-LED-002', 1, now_iso, now_iso),
        ('PTY-005', 'RAJASTHAN OIL MILLS, SRI GANGANAGAR', 'Rajasthan Oil Mills', 'rajasthan oil mills sri ganganagar', 'SELLER', 'Sri Ganganagar, Rajasthan', 'Grain Market Complex, Opp New Mandi', 'Sri Ganganagar', 'Rajasthan', 'Suresh Bansal', '+91 94142 88990', 'raj.oil@example.com', '08AAACR5544N1Z1', 'AAACR5544N', 'State Bank of India', '10928374650', 'SBIN0000718', 'Sri Ganganagar Main Branch', raj_contacts, 40.0, 40.0, 1, 750000.0, 'Established local expeller and solvent plant', 'BSY-LED-005', 1, now_iso, now_iso),
        ('PTY-001', 'HARYANA INDUSTRIES, PANCHKULA', 'Haryana Industries', 'haryana industries panchkula', 'BOTH', 'Panchkula, Haryana', 'Plot 45, Industrial Area Phase 1', 'Panchkula', 'Haryana', 'Rajesh Gupta', '+91 98120 45678', 'haryana.ind@example.com', '06AAACH2234M1Z2', 'AAACH2234M', 'ICICI Bank', '001205019283', 'ICIC0000012', 'Panchkula Sector 9 Branch', haryana_contacts, 50.0, 50.0, 1, 500000.0, 'Leading northern packaging and wholesale unit', 'BSY-LED-001', 1, now_iso, now_iso),
        ('PTY-004', 'SHAKTI NUTRITIONS PVT. LTD.', 'Shakti Nutritions', 'shakti nutritions pvt ltd', 'BUYER', 'Rewari, Haryana', 'NH-8, Packaging Zone', 'Rewari', 'Haryana', 'Amit Sharma', '+91 98765 43210', 'shakti.nutritions@example.com', '06AABCS1122K1Z9', 'AABCS1122K', 'Axis Bank', '918020038471293', 'UTIB0000219', 'Rewari Industrial Area Branch', shakti_contacts, 50.0, 50.0, 1, 1200000.0, 'Institutional consumer and consumer packager', 'BSY-LED-004', 1, now_iso, now_iso),
        ('PTY-006', 'KUBER EDIBLES, HISAR', 'Kuber Edibles', 'kuber edibles hisar', 'BUYER', 'Hisar, Haryana', 'Barwala Road Mandi', 'Hisar', 'Haryana', 'Praveen Jindal', '+91 99912 33445', 'kuber.hisar@example.com', '06AAACK8877L1Z6', 'AAACK8877L', 'Bank of Baroda', '27890200001827', 'BARB0HISARX', 'Hisar Mandi Gate Branch', kuber_contacts, 50.0, 50.0, 1, 600000.0, 'Mustard cake and oil wholesaler', 'BSY-LED-006', 1, now_iso, now_iso),
        ('PTY-007', 'SHREE GANESH AGRO TRADERS, ALWAR', 'Shree Ganesh Agro', 'shree ganesh agro traders alwar', 'BOTH', 'Alwar, Rajasthan', 'Old Subzi Mandi Yard', 'Alwar', 'Rajasthan', 'Ganesh Kumar', '+91 94141 55667', 'ganesh.agro@example.com', '08AABCS9988H1Z3', 'AABCS9988H', 'Punjab National Bank', '1892002100081234', 'PUNB0189200', 'Alwar Subzi Mandi Branch', alwar_contacts, 45.0, 45.0, 1, 400000.0, 'Regional mustard seed and edible oil broker-trader', 'BSY-LED-007', 1, now_iso, now_iso),
        ('PTY-003', 'M.L. NAGPAL INDUSTRIES, ANOUPGARH', 'M.L. Nagpal Ind', 'ml nagpal industries anoupgarh', 'BOTH', 'Anoupgarh, Rajasthan', 'Near Railway Siding', 'Anoupgarh', 'Rajasthan', 'Mohan Lal Nagpal', '+91 98290 67890', 'mlnagpal@example.com', '08AACCM4567P1Z8', 'AACCM4567P', 'State Bank of India', '31920048172', 'SBIN0031205', 'Anoupgarh Town Branch', nagpal_contacts, 50.0, 50.0, 1, 800000.0, 'Intermediate processor & trader', 'BSY-LED-003', 1, now_iso, now_iso),
    ]
    cur.executemany("""
        INSERT OR REPLACE INTO parties (
            id, legal_name, trade_name, normalized_name, party_type, mandi_station, address, city, state,
            contact_person, phone, email, gstin, pan, bank_name, bank_account_no, bank_ifsc, bank_branch,
            contacts_json, default_buyer_brokerage_per_tonne,
            default_seller_brokerage_per_tonne, brokerage_enabled, credit_limit, notes,
            busy_ledger_id, is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, parties)

    # Backfill bank details on existing records if NULL or empty
    for p in parties:
        cur.execute("""
            UPDATE parties 
            SET bank_name = ?, bank_account_no = ?, bank_ifsc = ?, bank_branch = ?
            WHERE id = ? AND (bank_name IS NULL OR bank_name = '')
        """, (p[14], p[15], p[16], p[17], p[0]))

    # 4. Seed Live Market Benchmark Rates
    market_rates = [
        ('MR-001', 'Mustard Oil (Loose)', 'Sri Ganganagar Mandi', 15250.0, 75.0, 15300.0, 15150.0, 'QUINTAL', now_iso),
        ('MR-002', 'Mustard Cake (Kachi Ghani)', 'Sri Ganganagar Mandi', 2850.0, -15.0, 2890.0, 2840.0, 'QUINTAL', now_iso),
        ('MR-003', 'Refined Soya Oil', 'Kandla Port Benchmark', 12400.0, 40.0, 12450.0, 12320.0, 'QUINTAL', now_iso),
        ('MR-004', 'RBD Palm Oil', 'Kandla Port Benchmark', 10950.0, 10.0, 11000.0, 10900.0, 'QUINTAL', now_iso),
        ('MR-005', 'Cottonseed Oil (Wash)', 'Kadi / Beawar Mandi', 11800.0, 50.0, 11850.0, 11700.0, 'QUINTAL', now_iso),
    ]
    cur.executemany("""
        INSERT OR REPLACE INTO market_rates (
            id, commodity_name, mandi_station, benchmark_rate_qtl, change_today, high_rate, low_rate, unit, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, market_rates)

    # 5. Seed Authentic Ganesh & Company Bargains (BGN-001 through BGN-006)
    bargains_data = [
        {
            "id": "DL-BGN-006",
            "bgn_code": "BGN-006",
            "chain_id": "LOT-2026-006",
            "deal_date": "2026-07-04",
            "seller_id": "PTY-HARBANS",
            "buyer_id": "PTY-TERAI",
            "product_id": "PRD-006", # Mustard Oil (Loose)
            "quantity_qtl": 320.0, # 32 MT
            "quantity_tonnes": 32.0,
            "rate_per_qtl": 15250.0,
            "advance_payment_date": "2026-07-06",
            "delivery_condition": "Ex-Mill Delivery Lifting: 13/07/2026 to 16/07/2026",
            "delivery_date": "2026-07-16",
            "is_buyer_confirmed": 1,
            "is_seller_confirmed": 1,
            "status": "CONFIRMED",
            "notes": "Direct mill tanker lifting to Siliguri. High pungent kachi ghani quality."
        },
        {
            "id": "DL-BGN-005",
            "bgn_code": "BGN-005",
            "chain_id": "LOT-2026-005",
            "deal_date": "2026-07-03",
            "seller_id": "PTY-002", # NAGPAL ENTERPRISES
            "buyer_id": "PTY-004", # SHAKTI NUTRITIONS
            "product_id": "PRD-006",
            "quantity_qtl": 300.0, # 30 MT
            "quantity_tonnes": 30.0,
            "rate_per_qtl": 15200.0,
            "advance_payment_date": "2026-07-05",
            "delivery_condition": "Ready Ex-Mill Lifting: 08/07/2026 to 11/07/2026",
            "delivery_date": "2026-07-11",
            "is_buyer_confirmed": 1,
            "is_seller_confirmed": 1,
            "status": "CONFIRMED",
            "notes": "Payment against weighment slip and dispatch bilty."
        },
        {
            "id": "DL-BGN-004",
            "bgn_code": "BGN-004",
            "chain_id": "LOT-2026-004",
            "deal_date": "2026-07-02",
            "seller_id": "PTY-005", # RAJASTHAN OIL MILLS
            "buyer_id": "PTY-006", # KUBER EDIBLES
            "product_id": "PRD-002", # Mustard Cake
            "quantity_qtl": 400.0, # 40 MT
            "quantity_tonnes": 40.0,
            "rate_per_qtl": 2850.0,
            "advance_payment_date": "2026-07-04",
            "delivery_condition": "Immediate F.O.R Hisar Delivery via Truck Dispatch",
            "delivery_date": "2026-07-08",
            "is_buyer_confirmed": 1,
            "is_seller_confirmed": 1,
            "status": "CONFIRMED",
            "notes": "Oil content min 7.5%, moisture max 8%."
        },
        {
            "id": "DL-BGN-003",
            "bgn_code": "BGN-003",
            "chain_id": "LOT-2026-003",
            "deal_date": "2026-07-02",
            "seller_id": "PTY-HARBANS",
            "buyer_id": "PTY-007", # SHREE GANESH AGRO
            "product_id": "PRD-003", # Refined Soya
            "quantity_qtl": 250.0, # 25 MT
            "quantity_tonnes": 25.0,
            "rate_per_qtl": 12400.0,
            "advance_payment_date": "2026-07-04",
            "delivery_condition": "Tanker Loading Ex-Sangaria Plant",
            "delivery_date": "2026-07-09",
            "is_buyer_confirmed": 1,
            "is_seller_confirmed": 1,
            "status": "CONFIRMED",
            "notes": "Standard food-grade tanker cleanliness mandatory."
        },
        {
            "id": "DL-BGN-002",
            "bgn_code": "BGN-002",
            "chain_id": "LOT-2026-002B",
            "deal_date": "2026-07-01",
            "seller_id": "PTY-002", # NAGPAL ENTERPRISES
            "buyer_id": "PTY-001", # HARYANA INDUSTRIES
            "product_id": "PRD-006", # Mustard Oil Loose
            "quantity_qtl": 320.0, # 32 MT
            "quantity_tonnes": 32.0,
            "rate_per_qtl": 15150.0,
            "advance_payment_date": "2026-07-03",
            "delivery_condition": "Ex-Mill Lifting: 06/07/2026 to 09/07/2026",
            "delivery_date": "2026-07-09",
            "is_buyer_confirmed": 0,
            "is_seller_confirmed": 1,
            "status": "PENDING",
            "notes": "Awaiting buyer formal confirmation stamp."
        },
        {
            "id": "DL-BGN-001",
            "bgn_code": "BGN-001",
            "chain_id": "LOT-2026-001B",
            "deal_date": "2026-07-01",
            "seller_id": "PTY-005", # RAJASTHAN OIL MILLS
            "buyer_id": "PTY-TERAI", # TERAI ISPAT
            "product_id": "PRD-004", # RBD Palm Oil
            "quantity_qtl": 200.0, # 20 MT
            "quantity_tonnes": 20.0,
            "rate_per_qtl": 10950.0,
            "advance_payment_date": "2026-07-03",
            "delivery_condition": "Kandla Tanker Direct Delivery to Siliguri",
            "delivery_date": "2026-07-12",
            "is_buyer_confirmed": 1,
            "is_seller_confirmed": 1,
            "status": "CONFIRMED",
            "notes": "Transit risk under buyer insurance policy."
        }
    ]

    for bg in bargains_data:
        # Create lot chain for the bargain
        cur.execute("""
            INSERT OR REPLACE INTO deal_chains (
                id, initial_deal_id, product_id, initial_quantity_qtl, remaining_unresold_quantity_qtl,
                original_bill_seller_id, final_bill_buyer_id, final_billing_rate_qtl, final_gst_treatment,
                status, approval_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 0.0, ?, ?, ?, 'PLUS_GST', 'READY_FOR_BILLING', 'APPROVED', ?, ?)
        """, (
            bg['chain_id'], bg['id'], bg['product_id'], bg['quantity_qtl'],
            bg['seller_id'], bg['buyer_id'], bg['rate_per_qtl'],
            bg['deal_date'] + "T10:00:00", bg['deal_date'] + "T10:00:00"
        ))

        # Calculate brokerage
        brok = calculate_brokerage(bg['quantity_tonnes'], 50.0, 50.0)

        # Insert deal
        cur.execute("""
            INSERT OR REPLACE INTO deals (
                id, bgn_code, chain_id, link_sequence, parent_deal_id, deal_date, seller_id, buyer_id, product_id,
                quantity_qtl, quantity_tonnes, rate_per_qtl, authorized_selling_rate_qtl,
                gst_applicable, gst_percentage, is_rate_inclusive_gst, delivery_date,
                advance_payment_date, delivery_condition, is_buyer_confirmed, is_seller_confirmed,
                buyer_brokerage_rate_per_tonne, seller_brokerage_rate_per_tonne,
                buyer_brokerage_amount, seller_brokerage_amount, total_brokerage_amount,
                price_diff_per_qtl, price_diff_profit, delivery_status, status,
                is_brokerage_overridden, brokerage_override_reason, notes, is_deleted,
                created_by, created_at, updated_at
            ) VALUES (?, ?, ?, 1, NULL, ?, ?, ?, ?, ?, ?, ?, 0.0, 1, 5.0, 0, ?, ?, ?, ?, ?, 50.0, 50.0, ?, ?, ?, 0.0, 0.0, 'PENDING', ?, 0, '', ?, 0, 'Sanjay Kumar Aggarwal', ?, ?)
        """, (
            bg['id'], bg['bgn_code'], bg['chain_id'], bg['deal_date'],
            bg['seller_id'], bg['buyer_id'], bg['product_id'],
            bg['quantity_qtl'], bg['quantity_tonnes'], bg['rate_per_qtl'],
            bg['delivery_date'], bg['advance_payment_date'], bg['delivery_condition'],
            bg['is_buyer_confirmed'], bg['is_seller_confirmed'],
            float(brok['buyer_brokerage']), float(brok['seller_brokerage']), float(brok['total_brokerage']),
            bg['status'], bg['notes'],
            bg['deal_date'] + "T10:00:00", bg['deal_date'] + "T10:00:00"
        ))

        # Direct Billing Instruction
        tax_calc = calculate_taxable_and_gst(bg['quantity_qtl'], bg['rate_per_qtl'], True, 5.0)
        cur.execute("SELECT legal_name FROM parties WHERE id = ?", (bg['seller_id'],))
        s_name = cur.fetchone()['legal_name']
        cur.execute("SELECT legal_name FROM parties WHERE id = ?", (bg['buyer_id'],))
        b_name = cur.fetchone()['legal_name']
        cur.execute("SELECT name FROM products WHERE id = ?", (bg['product_id'],))
        p_name = cur.fetchone()['name']

        cur.execute("""
            INSERT OR REPLACE INTO billing_instructions (
                id, chain_id, original_seller_id, final_buyer_id, product_id,
                quantity_qtl, rate_per_qtl, gst_applicable, gst_percentage,
                taxable_value, gst_amount, total_value, delivery_date,
                instruction_text, approval_status, approved_by, approved_at, remarks,
                export_status, export_timestamp, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'APPROVED', 'Sanjay Kumar Aggarwal', ?, ?, 'UNEXPORTED', NULL, ?)
        """, (
            f"BI-{bg['bgn_code']}", bg['chain_id'], bg['seller_id'], bg['buyer_id'], bg['product_id'],
            bg['quantity_qtl'], bg['rate_per_qtl'], 1, 5.0,
            float(tax_calc['taxable_value']), float(tax_calc['gst_amount']), float(tax_calc['total_value']), bg['delivery_date'],
            f"{s_name} will issue direct bill to {b_name} for {bg['quantity_qtl']:g} Qtl {p_name} @ ₹{bg['rate_per_qtl']:,.2f}/Qtl + GST.",
            bg['deal_date'] + "T11:00:00", f"Confirmed for {bg['bgn_code']}", bg['deal_date'] + "T10:00:00"
        ))

        # Ledger entries for brokerage
        cur.execute("""
            INSERT OR REPLACE INTO brokerage_ledger (id, party_id, deal_id, chain_id, entry_type, amount, reference_no, entry_date, notes, created_by, created_at)
            VALUES (?, ?, ?, ?, 'BROKERAGE_DUE_BUYER', ?, ?, ?, ?, 'Sanjay Kumar Aggarwal', ?)
        """, (f"LED-{bg['bgn_code']}-B", bg['buyer_id'], bg['id'], bg['chain_id'], float(brok['buyer_brokerage']), bg['bgn_code'], bg['deal_date'], f"Brokerage due on purchase of {bg['quantity_tonnes']:g} MT {p_name}", bg['deal_date'] + "T10:00:00"))

        cur.execute("""
            INSERT OR REPLACE INTO brokerage_ledger (id, party_id, deal_id, chain_id, entry_type, amount, reference_no, entry_date, notes, created_by, created_at)
            VALUES (?, ?, ?, ?, 'BROKERAGE_DUE_SELLER', ?, ?, ?, ?, 'Sanjay Kumar Aggarwal', ?)
        """, (f"LED-{bg['bgn_code']}-S", bg['seller_id'], bg['id'], bg['chain_id'], float(brok['seller_brokerage']), bg['bgn_code'], bg['deal_date'], f"Brokerage due on sale of {bg['quantity_tonnes']:g} MT {p_name}", bg['deal_date'] + "T10:00:00"))

    # 6. Seed Dispatch Logs (WhatsApp / Email trails)
    dispatch_logs = [
        ('DSP-001', 'DL-BGN-006', 'BUYER', 'TERAI ISPAT AND TRADING CO.', 'WHATSAPP', '+91 98320 11223', 'Bargain Confirmation [BGN-006]: 32 MT Mustard Oil @ ₹15,250 + GST', 'SENT', 'Sanjay Kumar Aggarwal', '2026-07-04T10:15:00'),
        ('DSP-002', 'DL-BGN-006', 'SELLER', 'HARBANS INDUSTRIES, SANGARIA', 'WHATSAPP', '+91 94140 51234', 'Bargain Confirmation [BGN-006]: 32 MT Mustard Oil @ ₹15,250 + GST', 'SENT', 'Sanjay Kumar Aggarwal', '2026-07-04T10:16:00'),
        ('DSP-003', 'DL-BGN-006', 'BUYER', 'TERAI ISPAT AND TRADING CO.', 'EMAIL', 'binod@teraitrading.com', 'Official Bargain Confirmation - BGN-006 - Ganesh & Company', 'SENT', 'Sanjay Kumar Aggarwal', '2026-07-04T10:20:00'),
        ('DSP-004', 'DL-BGN-005', 'BUYER', 'SHAKTI NUTRITIONS PVT. LTD.', 'WHATSAPP', '+91 98765 43210', 'Bargain Confirmation [BGN-005]: 30 MT Mustard Oil @ ₹15,200 + GST', 'SENT', 'Sanjay Kumar Aggarwal', '2026-07-03T11:45:00'),
        ('DSP-005', 'DL-BGN-005', 'SELLER', 'NAGPAL ENTERPRISES PVT. LTD.', 'WHATSAPP', '+91 94140 12345', 'Bargain Confirmation [BGN-005]: 30 MT Mustard Oil @ ₹15,200 + GST', 'SENT', 'Sanjay Kumar Aggarwal', '2026-07-03T11:46:00'),
        ('DSP-006', 'DL-BGN-004', 'BUYER', 'KUBER EDIBLES, HISAR', 'WHATSAPP', '+91 99912 33445', 'Bargain Confirmation [BGN-004]: 40 MT Mustard Cake @ ₹2,850 + GST', 'SENT', 'Sanjay Kumar Aggarwal', '2026-07-02T14:30:00'),
    ]
    cur.executemany("""
        INSERT OR REPLACE INTO dispatch_logs (
            id, deal_id, recipient_type, recipient_name, channel, phone_or_email, message_preview, status, sent_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, dispatch_logs)

    # 7. Seed Mandatory Acceptance Worked Example (LOT-2026-001) for backwards test compatibility
    chain_id = "LOT-2026-001"
    cur.execute("""
        INSERT OR REPLACE INTO deal_chains (id, initial_deal_id, product_id, initial_quantity_qtl, remaining_unresold_quantity_qtl, original_bill_seller_id, final_bill_buyer_id, final_billing_rate_qtl, final_gst_treatment, status, approval_status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        chain_id, "DL-2026-0001", "PRD-001", 320.0, 0.0,
        "PTY-002", "PTY-004", 16700.0, "PLUS_GST", "READY_FOR_BILLING", "APPROVED", "2026-07-01T10:00:00", "2026-08-11T14:30:00"
    ))

    # Deal 1: 01/07/2026 - Haryana Industries purchases from Nagpal Enterprises
    d1_calc_brok = calculate_brokerage(32, 50, 50)
    cur.execute("""
        INSERT OR REPLACE INTO deals (
            id, bgn_code, chain_id, link_sequence, parent_deal_id, deal_date, seller_id, buyer_id, product_id,
            quantity_qtl, quantity_tonnes, rate_per_qtl, authorized_selling_rate_qtl,
            gst_applicable, gst_percentage, is_rate_inclusive_gst, delivery_date,
            advance_payment_date, delivery_condition, is_buyer_confirmed, is_seller_confirmed,
            buyer_brokerage_rate_per_tonne, seller_brokerage_rate_per_tonne,
            buyer_brokerage_amount, seller_brokerage_amount, total_brokerage_amount,
            price_diff_per_qtl, price_diff_profit, delivery_status, status,
            is_brokerage_overridden, brokerage_override_reason, notes, is_deleted,
            created_by, created_at, updated_at
        ) VALUES (?, 'DL-2026-0001', ?, 1, NULL, ?, ?, ?, ?, ?, ?, ?, 0.0, 1, 5.0, 0, ?, '2026-07-03', 'Ex-Mill Lifting', 1, 1, 50.0, 50.0, ?, ?, ?, 0.0, 0.0, 'DELIVERED', 'CONFIRMED', 0, '', 'Initial bulk contract 320 quintals (32 tonnes)', 0, 'USR-002', '2026-07-01T10:00:00', '2026-07-01T10:00:00')
    """, (
        "DL-2026-0001", chain_id, "2026-07-01", "PTY-002", "PTY-001", "PRD-001",
        320.0, 32.0, 15700.0, "2026-07-31",
        float(d1_calc_brok['buyer_brokerage']), float(d1_calc_brok['seller_brokerage']), float(d1_calc_brok['total_brokerage'])
    ))

    # Link 1 (Deal 2): 18/07/2026 - Haryana Industries instructs resale @ 16,450. Sold to M.L. Nagpal @ 16,475 + GST
    d2_diff = calculate_price_difference(16475, 16450, 320)
    d2_brok = calculate_brokerage(32, 50, 50)
    cur.execute("""
        INSERT OR REPLACE INTO deals (
            id, bgn_code, chain_id, link_sequence, parent_deal_id, deal_date, seller_id, buyer_id, product_id,
            quantity_qtl, quantity_tonnes, rate_per_qtl, authorized_selling_rate_qtl,
            gst_applicable, gst_percentage, is_rate_inclusive_gst, delivery_date,
            advance_payment_date, delivery_condition, is_buyer_confirmed, is_seller_confirmed,
            buyer_brokerage_rate_per_tonne, seller_brokerage_rate_per_tonne,
            buyer_brokerage_amount, seller_brokerage_amount, total_brokerage_amount,
            price_diff_per_qtl, price_diff_profit, delivery_status, status,
            is_brokerage_overridden, brokerage_override_reason, notes, is_deleted,
            created_by, created_at, updated_at
        ) VALUES (?, 'DL-2026-0002', ?, 2, 'DL-2026-0001', ?, ?, ?, ?, ?, ?, ?, 16450.0, 1, 5.0, 0, ?, '2026-07-20', 'Ex-Mill Delivery', 1, 1, 50.0, 50.0, ?, ?, ?, ?, ?, 'DELIVERED', 'CONFIRMED', 0, '', 'Resale instructed by Haryana Ind @ 16450/qtl, executed @ 16475/qtl', 0, 'USR-002', '2026-07-18T11:30:00', '2026-07-18T11:30:00')
    """, (
        "DL-2026-0002", chain_id, "2026-07-18", "PTY-001", "PTY-003", "PRD-001",
        320.0, 32.0, 16475.0, "2026-07-31",
        float(d2_brok['buyer_brokerage']), float(d2_brok['seller_brokerage']), float(d2_brok['total_brokerage']),
        float(d2_diff['price_diff_per_qtl']), float(d2_diff['price_diff_profit'])
    ))

    # Link 2 (Deal 3): 30/07/2026 -> 11/08/2026 - M.L. Nagpal instructs @ 16,475. Sold to Shakti Nutritions @ 16,700 + GST
    d3_diff = calculate_price_difference(16700, 16475, 320)
    d3_brok = calculate_brokerage(32, 50, 50)
    cur.execute("""
        INSERT OR REPLACE INTO deals (
            id, bgn_code, chain_id, link_sequence, parent_deal_id, deal_date, seller_id, buyer_id, product_id,
            quantity_qtl, quantity_tonnes, rate_per_qtl, authorized_selling_rate_qtl,
            gst_applicable, gst_percentage, is_rate_inclusive_gst, delivery_date,
            advance_payment_date, delivery_condition, is_buyer_confirmed, is_seller_confirmed,
            buyer_brokerage_rate_per_tonne, seller_brokerage_rate_per_tonne,
            buyer_brokerage_amount, seller_brokerage_amount, total_brokerage_amount,
            price_diff_per_qtl, price_diff_profit, delivery_status, status,
            is_brokerage_overridden, brokerage_override_reason, notes, is_deleted,
            created_by, created_at, updated_at
        ) VALUES (?, 'DL-2026-0003', ?, 3, 'DL-2026-0002', ?, ?, ?, ?, ?, ?, ?, 16475.0, 1, 5.0, 0, ?, '2026-08-01', 'Direct Mill Delivery', 1, 1, 50.0, 50.0, ?, ?, ?, ?, ?, 'DELIVERED', 'CONFIRMED', 0, '', 'Final resale instructed by M.L. Nagpal @ 16475/qtl, executed to Shakti Nutritions @ 16700/qtl', 0, 'USR-002', '2026-07-30T16:00:00', '2026-08-11T14:30:00')
    """, (
        "DL-2026-0003", chain_id, "2026-07-30", "PTY-003", "PTY-004", "PRD-001",
        320.0, 32.0, 16700.0, "2026-08-11",
        float(d3_brok['buyer_brokerage']), float(d3_brok['seller_brokerage']), float(d3_brok['total_brokerage']),
        float(d3_diff['price_diff_per_qtl']), float(d3_diff['price_diff_profit'])
    ))

    # Billing instruction for LOT-2026-001
    d3_tax = calculate_taxable_and_gst(320, 16700, True, 5.0)
    cur.execute("""
        INSERT OR REPLACE INTO billing_instructions (
            id, chain_id, original_seller_id, final_buyer_id, product_id,
            quantity_qtl, rate_per_qtl, gst_applicable, gst_percentage,
            taxable_value, gst_amount, total_value, delivery_date,
            instruction_text, approval_status, approved_by, approved_at, remarks,
            export_status, export_timestamp, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'APPROVED', 'USR-001', '2026-08-12T10:00:00', 'Confirmed by Accounts and both parties', 'UNEXPORTED', NULL, '2026-08-11T14:30:00')
    """, (
        "BI-2026-0001", chain_id, "PTY-002", "PTY-004", "PRD-001",
        320.0, 16700.0, 1, 5.0,
        float(d3_tax['taxable_value']), float(d3_tax['gst_amount']), float(d3_tax['total_value']), "2026-08-11",
        "NAGPAL ENTERPRISES PVT. LTD., ANOUPGARH will issue a direct bill to SHAKTI NUTRITIONS PVT. LTD. for 320 quintals of M.OIL at ₹16,700.00 + GST per quintal."
    ))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    seed_all(reset=True)
    print("Database seeded successfully with master records, bargains, and worked example!")
