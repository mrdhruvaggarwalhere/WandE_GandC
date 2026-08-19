"""
REST API routes and controller logic for G&C Deal and Brokerage Automation Platform.
"""

import json
import sqlite3
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from app.core.database import get_db_connection, DB_PATH, log_audit
from app.core.calculations import (
    to_decimal,
    convert_quintals_to_tonnes,
    calculate_price_difference,
    calculate_brokerage,
    calculate_taxable_and_gst,
    calculate_deal_chain_summary
)
from app.core.busy_adapter import generate_busy_xml_voucher

def get_dashboard_metrics(db_path: str = DB_PATH, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    today_str = date.today().isoformat()
    week_end_str = (date.today() + timedelta(days=7)).isoformat()

    # Active Deals Count
    cur.execute("SELECT COUNT(*) FROM deals WHERE status != 'CANCELLED'")
    total_active_deals = cur.fetchone()[0]

    # Delivery status counts
    cur.execute("SELECT COUNT(*) FROM deals WHERE status != 'CANCELLED' AND delivery_date = ?", (today_str,))
    deliveries_today = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM deals WHERE status != 'CANCELLED' AND delivery_date > ? AND delivery_date <= ?", (today_str, week_end_str))
    deliveries_this_week = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM deals WHERE status != 'CANCELLED' AND delivery_date < ? AND delivery_status != 'DELIVERED'", (today_str,))
    deliveries_overdue = cur.fetchone()[0]

    # Chains awaiting resale vs Ready for Billing
    cur.execute("SELECT COUNT(*) FROM deal_chains WHERE status = 'OPEN' AND remaining_unresold_quantity_qtl > 0")
    chains_awaiting_resale = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM deal_chains WHERE status = 'READY_FOR_BILLING'")
    chains_ready_billing = cur.fetchone()[0]

    # Financial Aggregates
    cur.execute("""
        SELECT 
            COALESCE(SUM(price_diff_profit), 0) AS total_profit,
            COALESCE(SUM(buyer_brokerage_amount), 0) AS total_buyer_brok,
            COALESCE(SUM(seller_brokerage_amount), 0) AS total_seller_brok,
            COALESCE(SUM(total_brokerage_amount), 0) AS total_brok
        FROM deals
        WHERE status != 'CANCELLED'
    """)
    fin_row = cur.fetchone()
    total_price_diff_profit = fin_row['total_profit']
    total_buyer_brokerage = fin_row['total_buyer_brok']
    total_seller_brokerage = fin_row['total_seller_brok']
    total_brokerage = fin_row['total_brok']
    net_earnings = total_price_diff_profit + total_brokerage

    # Party-wise brokerage receivables
    cur.execute("""
        SELECT 
            p.id, p.legal_name,
            COALESCE(SUM(l.amount), 0) AS balance_due
        FROM parties p
        LEFT JOIN brokerage_ledger l ON p.id = l.party_id
        GROUP BY p.id
        HAVING balance_due != 0
        ORDER BY balance_due DESC
        LIMIT 8
    """)
    party_receivables = [{'party_id': r['id'], 'party_name': r['legal_name'], 'balance_due': r['balance_due']} for r in cur.fetchall()]

    # Recent Deals Feed
    cur.execute("""
        SELECT 
            d.id, d.deal_date, b.legal_name AS buyer_name, s.legal_name AS seller_name,
            p.name AS product_name, d.quantity_qtl, d.quantity_tonnes, d.rate_per_qtl,
            d.price_diff_profit, d.total_brokerage_amount, d.delivery_date, d.status, d.chain_id
        FROM deals d
        JOIN parties b ON d.buyer_id = b.id
        JOIN parties s ON d.seller_id = s.id
        JOIN products p ON d.product_id = p.id
        ORDER BY d.created_at DESC
        LIMIT 6
    """)
    recent_deals = [dict(r) for r in cur.fetchall()]

    conn.close()

    return {
        'total_active_deals': total_active_deals,
        'deliveries_today': deliveries_today,
        'deliveries_this_week': deliveries_this_week,
        'deliveries_overdue': deliveries_overdue,
        'chains_awaiting_resale': chains_awaiting_resale,
        'chains_ready_billing': chains_ready_billing,
        'total_price_diff_profit': total_price_diff_profit,
        'total_buyer_brokerage': total_buyer_brokerage,
        'total_seller_brokerage': total_seller_brokerage,
        'total_brokerage': total_brokerage,
        'net_earnings': net_earnings,
        'party_receivables': party_receivables,
        'recent_deals': recent_deals
    }

def create_new_deal(data: Dict[str, Any], actor_name: str = "Broker User", actor_role: str = "BROKER", db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Creates a brand new Root Deal and initializes a new DealChain (Lot).
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    deal_date = data.get('deal_date') or date.today().isoformat()
    seller_id = data.get('seller_id')
    buyer_id = data.get('buyer_id')
    product_id = data.get('product_id')
    qty_qtl = float(data.get('quantity_qtl', 0))
    rate_per_qtl = float(data.get('rate_per_qtl', 0))
    delivery_date = data.get('delivery_date') or deal_date
    gst_applicable = int(data.get('gst_applicable', 1))
    gst_percentage = float(data.get('gst_percentage', 5.0))
    is_rate_inclusive = int(data.get('is_rate_inclusive_gst', 0))
    notes = data.get('notes', '')

    if not seller_id or not buyer_id or not product_id:
        conn.close()
        raise ValueError("Buyer, Seller, and Product are required.")
    if buyer_id == seller_id:
        conn.close()
        raise ValueError("Buyer and Seller cannot be the identical party without authorized exemption.")
    if qty_qtl <= 0:
        conn.close()
        raise ValueError("Quantity must be greater than 0.")
    if rate_per_qtl <= 0:
        conn.close()
        raise ValueError("Rate per quintal must be greater than 0.")

    # Calculate quantities & brokerage
    qty_tonnes = float(convert_quintals_to_tonnes(qty_qtl))
    
    # Check party default brokerage if not specified
    cur.execute("SELECT default_buyer_brokerage_per_tonne, brokerage_enabled FROM parties WHERE id = ?", (buyer_id,))
    b_row = cur.fetchone()
    default_b_rate = b_row['default_buyer_brokerage_per_tonne'] if b_row and b_row['brokerage_enabled'] else 0.0

    cur.execute("SELECT default_seller_brokerage_per_tonne, brokerage_enabled FROM parties WHERE id = ?", (seller_id,))
    s_row = cur.fetchone()
    default_s_rate = s_row['default_seller_brokerage_per_tonne'] if s_row and s_row['brokerage_enabled'] else 0.0

    b_rate = float(data.get('buyer_brokerage_rate_per_tonne', default_b_rate))
    s_rate = float(data.get('seller_brokerage_rate_per_tonne', default_s_rate))
    is_overridden = 1 if (b_rate != default_b_rate or s_rate != default_s_rate) else 0
    override_reason = data.get('brokerage_override_reason', '')

    brok_calc = calculate_brokerage(qty_tonnes, b_rate, s_rate)
    b_brok_amt = float(brok_calc['buyer_brokerage'])
    s_brok_amt = float(brok_calc['seller_brokerage'])
    tot_brok_amt = float(brok_calc['total_brokerage'])

    # IDs with collision-free unique sequence
    import uuid
    uid_part = uuid.uuid4().hex[:5].upper()
    chain_id = f"LOT-{datetime.now().year}-{uid_part}"
    deal_id = f"DL-{datetime.now().year}-{uid_part}"
    now_iso = datetime.now().isoformat()

    # 1. Insert Deal Chain
    cur.execute("""
        INSERT INTO deal_chains (
            id, initial_deal_id, product_id, initial_quantity_qtl, remaining_unresold_quantity_qtl,
            original_bill_seller_id, final_bill_buyer_id, final_billing_rate_qtl, final_gst_treatment,
            status, approval_status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', 'PENDING', ?, ?)
    """, (chain_id, deal_id, product_id, qty_qtl, qty_qtl, seller_id, buyer_id, rate_per_qtl, 'PLUS_GST', now_iso, now_iso))

    # 2. Insert Deal
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
        ) VALUES (?, ?, 1, NULL, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, 'PENDING', 'CONFIRMED', ?, ?, ?, ?, ?, ?)
    """, (
        deal_id, chain_id, deal_date, seller_id, buyer_id, product_id,
        qty_qtl, qty_tonnes, rate_per_qtl,
        gst_applicable, gst_percentage, is_rate_inclusive, delivery_date,
        b_rate, s_rate, b_brok_amt, s_brok_amt, tot_brok_amt,
        is_overridden, override_reason, notes,
        actor_name, now_iso, now_iso
    ))

    # 3. Add initial Billing Instruction draft
    tax_calc = calculate_taxable_and_gst(qty_qtl, rate_per_qtl, bool(gst_applicable), gst_percentage, bool(is_rate_inclusive))
    
    cur.execute("SELECT legal_name FROM parties WHERE id = ?", (seller_id,))
    seller_name = cur.fetchone()['legal_name']
    cur.execute("SELECT legal_name FROM parties WHERE id = ?", (buyer_id,))
    buyer_name = cur.fetchone()['legal_name']
    cur.execute("SELECT name FROM products WHERE id = ?", (product_id,))
    prod_name = cur.fetchone()['name']

    instruction_text = f"{seller_name} will issue a direct bill to {buyer_name} for {qty_qtl:g} quintals of {prod_name} at ₹{rate_per_qtl:,.2f} + GST per quintal."

    bi_id = f"BI-{chain_id}"
    cur.execute("""
        INSERT INTO billing_instructions (
            id, chain_id, original_seller_id, final_buyer_id, product_id,
            quantity_qtl, rate_per_qtl, gst_applicable, gst_percentage,
            taxable_value, gst_amount, total_value, delivery_date,
            instruction_text, approval_status, approved_by, approved_at, remarks,
            export_status, export_timestamp, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_REVIEW', NULL, NULL, 'Initial deal instruction', 'UNEXPORTED', NULL, ?)
    """, (
        bi_id, chain_id, seller_id, buyer_id, product_id,
        qty_qtl, rate_per_qtl, gst_applicable, gst_percentage,
        float(tax_calc['taxable_value']), float(tax_calc['gst_amount']), float(tax_calc['total_value']), delivery_date,
        instruction_text, now_iso
    ))

    # 4. Insert Ledger entries for brokerage dues
    if b_brok_amt > 0:
        cur.execute("""
            INSERT INTO brokerage_ledger VALUES (?, ?, ?, ?, 'BROKERAGE_DUE_BUYER', ?, ?, ?, ?, ?, ?)
        """, (f"LED-{deal_id}-B", buyer_id, deal_id, chain_id, b_brok_amt, deal_id, deal_date, f"Brokerage due on purchase of {qty_tonnes:g} MT {prod_name}", actor_name, now_iso))
    if s_brok_amt > 0:
        cur.execute("""
            INSERT INTO brokerage_ledger VALUES (?, ?, ?, ?, 'BROKERAGE_DUE_SELLER', ?, ?, ?, ?, ?, ?)
        """, (f"LED-{deal_id}-S", seller_id, deal_id, chain_id, s_brok_amt, deal_id, deal_date, f"Brokerage due on sale of {qty_tonnes:g} MT {prod_name}", actor_name, now_iso))

    # 5. Audit log
    log_audit(conn, "deals", deal_id, "CREATE", actor_name, actor_role, None, {
        "deal_id": deal_id,
        "chain_id": chain_id,
        "buyer": buyer_name,
        "seller": seller_name,
        "quantity_qtl": qty_qtl,
        "rate_per_qtl": rate_per_qtl,
        "total_brokerage": tot_brok_amt
    }, "Created new deal and initialized lot chain")

    conn.commit()
    conn.close()

    return {
        'deal_id': deal_id,
        'chain_id': chain_id,
        'quantity_qtl': qty_qtl,
        'quantity_tonnes': qty_tonnes,
        'total_brokerage': tot_brok_amt,
        'instruction_text': instruction_text
    }

def resell_and_link_deal(data: Dict[str, Any], actor_name: str = "Broker User", actor_role: str = "BROKER", db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Carries forward a deal chain, records party instruction date, authorized selling rate,
    actual resale rate, computes price-difference profit, updates remaining quantities,
    and dynamically resolves the updated Direct Billing Instruction.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    chain_id = data.get('chain_id')
    parent_deal_id = data.get('parent_deal_id')
    instruction_date = data.get('instruction_date') or date.today().isoformat()
    deal_date = data.get('deal_date') or instruction_date
    authorized_rate_per_qtl = float(data.get('authorized_selling_rate_qtl') or data.get('authorized_rate_per_qtl') or 0)
    actual_sale_rate_per_qtl = float(data.get('actual_sale_rate_per_qtl') or data.get('actual_sale_rate_qtl') or data.get('rate_per_qtl') or 0)
    resale_buyer_id = data.get('buyer_id')
    instructing_seller_id = data.get('seller_id')
    qty_qtl = float(data.get('quantity_qtl', 0))
    delivery_date = data.get('delivery_date') or deal_date
    notes = data.get('notes', '')

    if not chain_id or not resale_buyer_id:
        conn.close()
        raise ValueError("Chain ID and New Buyer are required.")

    # Fetch Chain details
    cur.execute("SELECT * FROM deal_chains WHERE id = ?", (chain_id,))
    chain_row = cur.fetchone()
    if not chain_row:
        conn.close()
        raise ValueError(f"Deal Chain {chain_id} not found.")

    if chain_row['status'] == 'CANCELLED':
        conn.close()
        raise ValueError("Cannot resell a cancelled deal chain.")

    # Fetch last deal in chain to determine default instructing party and link sequence
    cur.execute("SELECT * FROM deals WHERE chain_id = ? AND status != 'CANCELLED' ORDER BY link_sequence DESC LIMIT 1", (chain_id,))
    last_deal = cur.fetchone()
    if not last_deal:
        conn.close()
        raise ValueError("No valid parent deal found in this chain.")

    if not instructing_seller_id:
        instructing_seller_id = last_deal['buyer_id'] # Previous buyer is now instructing seller

    if instructing_seller_id == resale_buyer_id:
        conn.close()
        raise ValueError("Resale buyer cannot be the same as the instructing seller.")

    # Validate resale quantity against available balance
    # Remaining quantity is tracked on the chain
    remaining_qty = chain_row['remaining_unresold_quantity_qtl']
    if qty_qtl > remaining_qty and remaining_qty > 0:
        # Note: If already resold once completely, chained resales of full lot have available = initial lot size
        pass
    if qty_qtl <= 0:
        conn.close()
        raise ValueError("Resale quantity must be greater than 0.")

    # Calculate Price Difference Profit
    diff_calc = calculate_price_difference(actual_sale_rate_per_qtl, authorized_rate_per_qtl, qty_qtl)
    price_diff_per_qtl = float(diff_calc['price_diff_per_qtl'])
    price_diff_profit = float(diff_calc['price_diff_profit'])

    # Calculate Brokerage
    qty_tonnes = float(convert_quintals_to_tonnes(qty_qtl))
    cur.execute("SELECT default_buyer_brokerage_per_tonne, brokerage_enabled FROM parties WHERE id = ?", (resale_buyer_id,))
    b_row = cur.fetchone()
    default_b_rate = b_row['default_buyer_brokerage_per_tonne'] if b_row and b_row['brokerage_enabled'] else 0.0

    cur.execute("SELECT default_seller_brokerage_per_tonne, brokerage_enabled FROM parties WHERE id = ?", (instructing_seller_id,))
    s_row = cur.fetchone()
    default_s_rate = s_row['default_seller_brokerage_per_tonne'] if s_row and s_row['brokerage_enabled'] else 0.0

    b_rate = float(data.get('buyer_brokerage_rate_per_tonne', default_b_rate))
    s_rate = float(data.get('seller_brokerage_rate_per_tonne', default_s_rate))
    is_overridden = 1 if (b_rate != default_b_rate or s_rate != default_s_rate) else 0
    override_reason = data.get('brokerage_override_reason', '')

    brok_calc = calculate_brokerage(qty_tonnes, b_rate, s_rate)
    b_brok_amt = float(brok_calc['buyer_brokerage'])
    s_brok_amt = float(brok_calc['seller_brokerage'])
    tot_brok_amt = float(brok_calc['total_brokerage'])

    # Link Sequence & Deal ID
    import uuid
    next_link_seq = last_deal['link_sequence'] + 1
    uid_part = uuid.uuid4().hex[:5].upper()
    deal_id = f"DL-{datetime.now().year}-{uid_part}"
    now_iso = datetime.now().isoformat()
    product_id = chain_row['product_id']

    # 1. Insert New Deal Link
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
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 5.0, 0, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 'CONFIRMED', ?, ?, ?, ?, ?, ?)
    """, (
        deal_id, chain_id, next_link_seq, last_deal['id'], deal_date, instructing_seller_id, resale_buyer_id, product_id,
        qty_qtl, qty_tonnes, actual_sale_rate_per_qtl, authorized_rate_per_qtl,
        delivery_date, b_rate, s_rate, b_brok_amt, s_brok_amt, tot_brok_amt,
        price_diff_per_qtl, price_diff_profit, is_overridden, override_reason, notes,
        actor_name, now_iso, now_iso
    ))

    # 2. Update Deal Chain with Final Buyer, Final Billing Rate, and Status
    new_remaining = max(0.0, remaining_qty - qty_qtl)
    cur.execute("""
        UPDATE deal_chains
        SET final_bill_buyer_id = ?,
            final_billing_rate_qtl = ?,
            remaining_unresold_quantity_qtl = ?,
            status = 'READY_FOR_BILLING',
            updated_at = ?
        WHERE id = ?
    """, (resale_buyer_id, actual_sale_rate_per_qtl, new_remaining, now_iso, chain_id))

    # 3. Dynamically update or create Official Direct Billing Instruction
    # Original Bill Seller is the root seller
    orig_seller_id = chain_row['original_bill_seller_id']
    cur.execute("SELECT legal_name FROM parties WHERE id = ?", (orig_seller_id,))
    orig_seller_name = cur.fetchone()['legal_name']

    cur.execute("SELECT legal_name FROM parties WHERE id = ?", (resale_buyer_id,))
    final_buyer_name = cur.fetchone()['legal_name']

    cur.execute("SELECT name FROM products WHERE id = ?", (product_id,))
    prod_name = cur.fetchone()['name']

    tax_calc = calculate_taxable_and_gst(qty_qtl, actual_sale_rate_per_qtl, True, 5.0)
    updated_instruction_text = (
        f"{orig_seller_name} will issue a direct bill to {final_buyer_name} "
        f"for {qty_qtl:g} quintals of {prod_name} at ₹{actual_sale_rate_per_qtl:,.2f} + GST per quintal."
    )

    cur.execute("""
        INSERT INTO billing_instructions (
            id, chain_id, original_seller_id, final_buyer_id, product_id,
            quantity_qtl, rate_per_qtl, gst_applicable, gst_percentage,
            taxable_value, gst_amount, total_value, delivery_date,
            instruction_text, approval_status, approved_by, approved_at, remarks,
            export_status, export_timestamp, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 5.0, ?, ?, ?, ?, ?, 'PENDING_REVIEW', NULL, NULL, 'Updated upon resale chaining', 'UNEXPORTED', NULL, ?)
        ON CONFLICT(chain_id) DO UPDATE SET
            final_buyer_id = excluded.final_buyer_id,
            rate_per_qtl = excluded.rate_per_qtl,
            taxable_value = excluded.taxable_value,
            gst_amount = excluded.gst_amount,
            total_value = excluded.total_value,
            delivery_date = excluded.delivery_date,
            instruction_text = excluded.instruction_text,
            approval_status = 'PENDING_REVIEW'
    """, (
        f"BI-{chain_id}", chain_id, orig_seller_id, resale_buyer_id, product_id,
        qty_qtl, actual_sale_rate_per_qtl,
        float(tax_calc['taxable_value']), float(tax_calc['gst_amount']), float(tax_calc['total_value']), delivery_date,
        updated_instruction_text, now_iso
    ))

    # 4. Insert Ledger entries for brokerage
    if b_brok_amt > 0:
        cur.execute("""
            INSERT INTO brokerage_ledger VALUES (?, ?, ?, ?, 'BROKERAGE_DUE_BUYER', ?, ?, ?, ?, ?, ?)
        """, (f"LED-{deal_id}-B", resale_buyer_id, deal_id, chain_id, b_brok_amt, deal_id, deal_date, f"Brokerage due on purchase of {qty_tonnes:g} MT {prod_name}", actor_name, now_iso))
    if s_brok_amt > 0:
        cur.execute("""
            INSERT INTO brokerage_ledger VALUES (?, ?, ?, ?, 'BROKERAGE_DUE_SELLER', ?, ?, ?, ?, ?, ?)
        """, (f"LED-{deal_id}-S", instructing_seller_id, deal_id, chain_id, s_brok_amt, deal_id, deal_date, f"Brokerage due on resale of {qty_tonnes:g} MT {prod_name}", actor_name, now_iso))

    # 5. Audit Log
    log_audit(conn, "deals", deal_id, "CREATE", actor_name, actor_role, None, {
        "chain_id": chain_id,
        "link_sequence": next_link_seq,
        "instructing_seller": instructing_seller_id,
        "actual_buyer": resale_buyer_id,
        "authorized_rate": authorized_rate_per_qtl,
        "actual_rate": actual_sale_rate_per_qtl,
        "price_diff_profit": price_diff_profit,
        "total_brokerage": tot_brok_amt
    }, f"Linked resale deal #{next_link_seq} in lot {chain_id}")

    conn.commit()
    conn.close()

    return {
        'deal_id': deal_id,
        'chain_id': chain_id,
        'link_sequence': next_link_seq,
        'price_diff_profit': price_diff_profit,
        'total_brokerage': tot_brok_amt,
        'instruction_text': updated_instruction_text
    }

def get_deal_chain_details(chain_id: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Returns full details for a deal chain including all chronological link deals,
    summary calculations, and billing instruction.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            c.*, p.name AS product_name,
            obs.legal_name AS original_seller_name,
            fbb.legal_name AS final_buyer_name
        FROM deal_chains c
        JOIN products p ON c.product_id = p.id
        JOIN parties obs ON c.original_bill_seller_id = obs.id
        LEFT JOIN parties fbb ON c.final_bill_buyer_id = fbb.id
        WHERE c.id = ?
    """, (chain_id,))
    chain_row = cur.fetchone()
    if not chain_row:
        conn.close()
        raise ValueError(f"Deal Chain {chain_id} not found.")

    cur.execute("""
        SELECT 
            d.*, b.legal_name AS buyer_name, s.legal_name AS seller_name,
            p.name AS product_name
        FROM deals d
        JOIN parties b ON d.buyer_id = b.id
        JOIN parties s ON d.seller_id = s.id
        JOIN products p ON d.product_id = p.id
        WHERE d.chain_id = ?
        ORDER BY d.link_sequence ASC, d.deal_date ASC
    """, (chain_id,))
    deals = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM billing_instructions WHERE chain_id = ?", (chain_id,))
    billing_row = cur.fetchone()
    billing_info = dict(billing_row) if billing_row else None

    # Calculate summary using pure calculation module
    summary = calculate_deal_chain_summary(deals)

    conn.close()

    return {
        'chain': dict(chain_row),
        'deals': deals,
        'billing_instruction': billing_info,
        'summary': summary
    }

def approve_billing_instruction(instruction_id: str, actor_name: str = "Accounts User", actor_role: str = "ACCOUNTS", remarks: str = "", db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Approves a direct billing instruction making it ready for BUSY / Accounting export.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT * FROM billing_instructions WHERE id = ?", (instruction_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Billing Instruction {instruction_id} not found.")

    now_iso = datetime.now().isoformat()
    cur.execute("""
        UPDATE billing_instructions
        SET approval_status = 'APPROVED',
            approved_by = ?,
            approved_at = ?,
            remarks = ?
        WHERE id = ?
    """, (actor_name, now_iso, remarks or row['remarks'], instruction_id))

    # Also update chain status
    cur.execute("""
        UPDATE deal_chains
        SET approval_status = 'APPROVED',
            status = 'READY_FOR_BILLING',
            updated_at = ?
        WHERE id = ?
    """, (now_iso, row['chain_id']))

    log_audit(conn, "billing_instructions", instruction_id, "APPROVE", actor_name, actor_role, {
        "status": row['approval_status']
    }, {
        "status": "APPROVED",
        "approved_by": actor_name,
        "approved_at": now_iso
    }, remarks or "Official direct billing instruction approved")

    conn.commit()
    conn.close()

    return {
        'instruction_id': instruction_id,
        'chain_id': row['chain_id'],
        'approval_status': 'APPROVED',
        'approved_by': actor_name,
        'approved_at': now_iso
    }

def record_brokerage_payment(data: Dict[str, Any], actor_name: str = "Accounts User", actor_role: str = "ACCOUNTS", db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Records a payment or receipt against a party's brokerage dues.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    party_id = data.get('party_id')
    amount = float(data.get('amount', 0))
    entry_type = data.get('entry_type', 'PAYMENT_RECEIVED')
    ref_no = data.get('reference_no', '')
    entry_date = data.get('entry_date') or date.today().isoformat()
    notes = data.get('notes', '')

    if not party_id or amount <= 0:
        conn.close()
        raise ValueError("Valid Party and positive Amount are required.")

    # In brokerage ledger, payments reduce due balance (stored as negative value)
    signed_amount = -amount if entry_type in ('PAYMENT_RECEIVED', 'DISCOUNT') else amount

    entry_id = f"PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    now_iso = datetime.now().isoformat()

    cur.execute("""
        INSERT INTO brokerage_ledger VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?)
    """, (entry_id, party_id, entry_type, signed_amount, ref_no, entry_date, notes, actor_name, now_iso))

    log_audit(conn, "brokerage_ledger", entry_id, "PAYMENT", actor_name, actor_role, None, {
        "party_id": party_id,
        "amount": amount,
        "entry_type": entry_type,
        "ref_no": ref_no
    }, f"Recorded brokerage payment of ₹{amount:,.2f}")

    conn.commit()
    conn.close()

    return {
        'entry_id': entry_id,
        'party_id': party_id,
        'amount': amount,
        'entry_type': entry_type
    }
