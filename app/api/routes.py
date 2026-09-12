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

    # Active Non-Deleted Deals Count
    cur.execute("SELECT COUNT(*) FROM deals WHERE status != 'CANCELLED' AND COALESCE(is_deleted, 0) = 0")
    total_active_deals = cur.fetchone()[0]

    # Active Parties Count
    cur.execute("SELECT COUNT(*) FROM parties WHERE is_active = 1")
    active_parties_count = cur.fetchone()[0]

    # Active Traded Volume MT
    cur.execute("SELECT COALESCE(SUM(quantity_tonnes), 0) FROM deals WHERE status != 'CANCELLED' AND COALESCE(is_deleted, 0) = 0")
    active_traded_volume_mt = float(cur.fetchone()[0])

    # Today's deals & Today's Volume
    cur.execute("SELECT COUNT(*), COALESCE(SUM(quantity_tonnes), 0) FROM deals WHERE deal_date = ? AND status != 'CANCELLED' AND COALESCE(is_deleted, 0) = 0", (today_str,))
    today_row = cur.fetchone()
    todays_deals_count = today_row[0]
    todays_traded_volume_mt = float(today_row[1])

    # Pending Confirmations (Unconfirmed by either party or status PENDING or reconfirmation required)
    cur.execute("""
        SELECT COUNT(*) FROM deals 
        WHERE status != 'CANCELLED' 
          AND COALESCE(is_deleted, 0) = 0 
          AND (status IN ('PENDING', 'UPDATED') OR is_buyer_confirmed = 0 OR is_seller_confirmed = 0 OR COALESCE(reconfirmation_required, 0) = 1)
    """)
    pending_confirmations_count = cur.fetchone()[0]

    # Delivery status counts
    cur.execute("SELECT COUNT(*) FROM deals WHERE status != 'CANCELLED' AND delivery_date = ? AND COALESCE(is_deleted, 0) = 0", (today_str,))
    deliveries_today = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM deals WHERE status != 'CANCELLED' AND delivery_date > ? AND delivery_date <= ? AND COALESCE(is_deleted, 0) = 0", (today_str, week_end_str))
    deliveries_this_week = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM deals WHERE status != 'CANCELLED' AND delivery_date < ? AND delivery_status != 'DELIVERED' AND COALESCE(is_deleted, 0) = 0", (today_str,))
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
        WHERE status != 'CANCELLED' AND COALESCE(is_deleted, 0) = 0
    """)
    fin_row = cur.fetchone()
    total_price_diff_profit = fin_row['total_profit']
    total_buyer_brokerage = 0.0
    total_seller_brokerage = 0.0
    total_brokerage = 0.0
    net_earnings = total_price_diff_profit

    # Commodity Volume Distribution
    cur.execute("""
        SELECT 
            p.id, p.name AS product_name,
            COUNT(d.id) AS deal_count,
            COALESCE(SUM(d.quantity_tonnes), 0) AS total_tonnes,
            COALESCE(SUM(d.quantity_qtl), 0) AS total_qtl
        FROM products p
        LEFT JOIN deals d ON p.id = d.product_id AND d.status != 'CANCELLED' AND COALESCE(d.is_deleted, 0) = 0
        GROUP BY p.id
        ORDER BY total_tonnes DESC
    """)
    commodity_rows = cur.fetchall()
    commodity_distribution = []
    total_commodity_tonnes = max(1.0, sum(float(r['total_tonnes']) for r in commodity_rows))
    for r in commodity_rows:
        t_mt = float(r['total_tonnes'])
        commodity_distribution.append({
            'product_id': r['id'],
            'product_name': r['product_name'],
            'deal_count': r['deal_count'],
            'total_tonnes': t_mt,
            'total_qtl': float(r['total_qtl']),
            'percentage': round((t_mt / total_commodity_tonnes) * 100, 1)
        })

    # Party-wise brokerage receivables (disabled per zero brokerage requirement)
    party_receivables = []

    # Live Bargains Stream / Recent Deals Feed with Mandi Stations & Counterparties
    cur.execute("""
        SELECT 
            d.id, COALESCE(d.bgn_code, d.id) AS bgn_code, d.deal_date,
            b.id AS buyer_id, b.legal_name AS buyer_name, COALESCE(b.mandi_station, b.city) AS buyer_station, b.phone AS buyer_phone,
            s.id AS seller_id, s.legal_name AS seller_name, COALESCE(s.mandi_station, s.city) AS seller_station, s.phone AS seller_phone,
            p.id AS product_id, p.name AS product_name,
            d.quantity_qtl, d.quantity_tonnes, d.rate_per_qtl,
            COALESCE(d.seller_rate, d.rate_per_qtl) AS seller_rate,
            COALESCE(d.buyer_rate, d.rate_per_qtl) AS buyer_rate,
            COALESCE(d.reconfirmation_required, 0) AS reconfirmation_required,
            d.advance_payment_date, d.delivery_condition,
            COALESCE(d.is_buyer_confirmed, 1) AS is_buyer_confirmed,
            COALESCE(d.is_seller_confirmed, 1) AS is_seller_confirmed,
            d.price_diff_profit, d.total_brokerage_amount, d.delivery_date, d.status, d.chain_id
        FROM deals d
        JOIN parties b ON d.buyer_id = b.id
        JOIN parties s ON d.seller_id = s.id
        JOIN products p ON d.product_id = p.id
        WHERE COALESCE(d.is_deleted, 0) = 0
        ORDER BY d.deal_date DESC, d.created_at DESC
        LIMIT 10
    """)
    recent_deals = [dict(r) for r in cur.fetchall()]

    conn.close()

    return {
        'total_active_deals': total_active_deals,
        'todays_deals_count': todays_deals_count,
        'todays_traded_volume_mt': todays_traded_volume_mt,
        'active_traded_volume_mt': active_traded_volume_mt,
        'active_parties_count': active_parties_count,
        'pending_confirmations_count': pending_confirmations_count,
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
        'commodity_distribution': commodity_distribution,
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
    seller_rate = float(data.get('seller_rate') or data.get('rate_per_qtl') or 0.0)
    buyer_rate = float(data.get('buyer_rate') or (data.get('rate_per_qtl') if 'rate_per_qtl' in data and 'buyer_rate' not in data else seller_rate))
    if seller_rate <= 0:
        seller_rate = float(data.get('rate_per_qtl', 0))
    if buyer_rate <= 0:
        buyer_rate = seller_rate
    rate_per_qtl = seller_rate

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
    if seller_rate <= 0 or buyer_rate <= 0:
        conn.close()
        raise ValueError("Seller Rate and Buyer Rate must be greater than 0.")

    # Calculate quantities & brokerage
    qty_tonnes = float(convert_quintals_to_tonnes(qty_qtl))
    
    # Brokerage calculations disabled completely per user requirement
    b_rate = 0.0
    s_rate = 0.0
    is_overridden = 0
    override_reason = ''
    b_brok_amt = 0.0
    s_brok_amt = 0.0
    tot_brok_amt = 0.0

    advance_payment_date = data.get('advance_payment_date') or deal_date
    delivery_condition = data.get('delivery_condition') or f"Ex-Mill Lifting {deal_date} to {delivery_date}"
    is_buyer_confirmed = int(data.get('is_buyer_confirmed', 1))
    is_seller_confirmed = int(data.get('is_seller_confirmed', 1))

    # IDs with collision-free unique sequence
    import uuid
    uid_part = uuid.uuid4().hex[:5].upper()
    chain_id = f"LOT-{datetime.now().year}-{uid_part}"
    deal_id = f"DL-{datetime.now().year}-{uid_part}"
    now_iso = datetime.now().isoformat()

    # Generate sequential BGN code if not provided
    bgn_code = data.get('bgn_code')
    if not bgn_code:
        cur.execute("SELECT COUNT(*) FROM deals")
        bgn_num = cur.fetchone()[0] + 1
        bgn_code = f"BGN-{bgn_num:03d}"

    # 1. Insert Deal Chain
    cur.execute("""
        INSERT INTO deal_chains (
            id, initial_deal_id, product_id, initial_quantity_qtl, remaining_unresold_quantity_qtl,
            original_bill_seller_id, final_bill_buyer_id, final_billing_rate_qtl, final_gst_treatment,
            status, approval_status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', 'PENDING', ?, ?)
    """, (chain_id, deal_id, product_id, qty_qtl, qty_qtl, seller_id, buyer_id, buyer_rate, 'PLUS_GST', now_iso, now_iso))

    # 2. Insert Deal
    cur.execute("""
        INSERT INTO deals (
            id, bgn_code, chain_id, link_sequence, parent_deal_id, deal_date, seller_id, buyer_id, product_id,
            quantity_qtl, quantity_tonnes, rate_per_qtl, seller_rate, buyer_rate, authorized_selling_rate_qtl,
            gst_applicable, gst_percentage, is_rate_inclusive_gst, delivery_date,
            advance_payment_date, delivery_condition, is_buyer_confirmed, is_seller_confirmed, reconfirmation_required,
            buyer_brokerage_rate_per_tonne, seller_brokerage_rate_per_tonne,
            buyer_brokerage_amount, seller_brokerage_amount, total_brokerage_amount,
            price_diff_per_qtl, price_diff_profit, delivery_status, status,
            is_brokerage_overridden, brokerage_override_reason, notes, is_deleted,
            created_by, created_at, updated_at
        ) VALUES (?, ?, ?, 1, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 0.0, 0.0, 'PENDING', 'CONFIRMED', ?, ?, ?, 0, ?, ?, ?)
    """, (
        deal_id, bgn_code, chain_id, deal_date, seller_id, buyer_id, product_id,
        qty_qtl, qty_tonnes, rate_per_qtl, seller_rate, buyer_rate,
        gst_applicable, gst_percentage, is_rate_inclusive, delivery_date,
        advance_payment_date, delivery_condition, is_buyer_confirmed, is_seller_confirmed,
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
    
    # Brokerage calculations disabled completely per user requirement
    b_rate = 0.0
    s_rate = 0.0
    is_overridden = 0
    override_reason = ''
    b_brok_amt = 0.0
    s_brok_amt = 0.0
    tot_brok_amt = 0.0

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

def get_party_profile(party_id: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Returns high-density party profile: master details, contacts hierarchy,
    KPI summary, full contract register, and commodity volume breakdown.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT * FROM parties WHERE id = ?", (party_id,))
    p_row = cur.fetchone()
    if not p_row:
        conn.close()
        raise ValueError(f"Party {party_id} not found.")

    party = dict(p_row)
    if party.get('contacts_json'):
        try:
            party['contacts'] = json.loads(party['contacts_json'])
        except Exception:
            party['contacts'] = []
    else:
        party['contacts'] = [
            {"name": party.get('contact_person') or "Authorized Signatory", "role": "Owner", "phone": party.get('phone') or "", "email": party.get('email') or ""}
        ]

    # Total Deals
    cur.execute("""
        SELECT COUNT(*) FROM deals 
        WHERE (buyer_id = ? OR seller_id = ?) AND COALESCE(is_deleted, 0) = 0
    """, (party_id, party_id))
    total_deals = cur.fetchone()[0]

    # Confirmed Volume (MT)
    cur.execute("""
        SELECT COALESCE(SUM(quantity_tonnes), 0) FROM deals 
        WHERE (buyer_id = ? OR seller_id = ?) AND status = 'CONFIRMED' AND COALESCE(is_deleted, 0) = 0
    """, (party_id, party_id))
    confirmed_volume_mt = float(cur.fetchone()[0])

    # Pending Deals
    cur.execute("""
        SELECT COUNT(*) FROM deals 
        WHERE (buyer_id = ? OR seller_id = ?) AND (status = 'PENDING' OR is_buyer_confirmed = 0 OR is_seller_confirmed = 0) AND COALESCE(is_deleted, 0) = 0
    """, (party_id, party_id))
    pending_deals = cur.fetchone()[0]

    # Brokerage calculations disabled
    balance_due = 0.0

    # Recent Deals for this party
    cur.execute("""
        SELECT 
            d.*, COALESCE(d.bgn_code, d.id) AS bgn_code,
            b.legal_name AS buyer_name, COALESCE(b.mandi_station, b.city) AS buyer_station,
            s.legal_name AS seller_name, COALESCE(s.mandi_station, s.city) AS seller_station,
            p.name AS product_name
        FROM deals d
        JOIN parties b ON d.buyer_id = b.id
        JOIN parties s ON d.seller_id = s.id
        JOIN products p ON d.product_id = p.id
        WHERE (d.buyer_id = ? OR d.seller_id = ?) AND COALESCE(d.is_deleted, 0) = 0
        ORDER BY d.deal_date DESC, d.created_at DESC
        LIMIT 20
    """, (party_id, party_id))
    deals = [dict(r) for r in cur.fetchall()]

    # Commodity volume breakdown for this party
    cur.execute("""
        SELECT 
            p.name AS product_name,
            COUNT(d.id) AS deal_count,
            COALESCE(SUM(d.quantity_tonnes), 0) AS total_tonnes
        FROM deals d
        JOIN products p ON d.product_id = p.id
        WHERE (d.buyer_id = ? OR d.seller_id = ?) AND COALESCE(d.is_deleted, 0) = 0
        GROUP BY p.id
        ORDER BY total_tonnes DESC
    """, (party_id, party_id))
    comm_rows = cur.fetchall()
    total_party_mt = max(0.1, sum(float(r['total_tonnes']) for r in comm_rows))
    commodity_history = []
    for r in comm_rows:
        mt = float(r['total_tonnes'])
        commodity_history.append({
            'product_name': r['product_name'],
            'deal_count': r['deal_count'],
            'total_tonnes': mt,
            'percentage': round((mt / total_party_mt) * 100, 1)
        })

    conn.close()

    return {
        'party': party,
        'kpis': {
            'total_deals': total_deals,
            'confirmed_volume_mt': confirmed_volume_mt,
            'pending_deals': pending_deals,
            'commodities_traded_count': len(commodity_history),
            'balance_due': balance_due
        },
        'contacts': party['contacts'],
        'deals': deals,
        'commodity_history': commodity_history
    }

def soft_delete_deal(deal_id: str, actor_name: str, actor_role: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Moves a deal to the Trash bin."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT * FROM deals WHERE id = ? OR bgn_code = ?", (deal_id, deal_id))
    deal = cur.fetchone()
    if not deal:
        conn.close()
        raise ValueError(f"Deal {deal_id} not found.")

    real_deal_id = deal['id']
    now_iso = datetime.now().isoformat()
    cur.execute("UPDATE deals SET is_deleted = 1, deleted_at = ?, updated_at = ? WHERE id = ?", (now_iso, now_iso, real_deal_id))

    log_audit(conn, "deals", real_deal_id, "TRASH", actor_name, actor_role, {
        "is_deleted": 0
    }, {
        "is_deleted": 1,
        "deleted_at": now_iso
    }, "Soft deleted to trash bin")

    conn.commit()
    conn.close()
    return {'deal_id': real_deal_id, 'is_deleted': 1, 'deleted_at': now_iso}

def restore_deal(deal_id: str, actor_name: str, actor_role: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Restores a soft-deleted deal from the Trash bin."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT * FROM deals WHERE id = ? OR bgn_code = ?", (deal_id, deal_id))
    deal = cur.fetchone()
    if not deal:
        conn.close()
        raise ValueError(f"Deal {deal_id} not found.")

    real_deal_id = deal['id']
    now_iso = datetime.now().isoformat()
    cur.execute("UPDATE deals SET is_deleted = 0, deleted_at = NULL, updated_at = ? WHERE id = ?", (now_iso, real_deal_id))

    log_audit(conn, "deals", real_deal_id, "RESTORE", actor_name, actor_role, {
        "is_deleted": 1
    }, {
        "is_deleted": 0
    }, "Restored deal from trash bin")

    conn.commit()
    conn.close()
    return {'deal_id': real_deal_id, 'is_deleted': 0}

def purge_deal_permanent(deal_id: str, actor_name: str, actor_role: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Permanently purges a deal and its ledger entries."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT * FROM deals WHERE id = ? OR bgn_code = ?", (deal_id, deal_id))
    deal = cur.fetchone()
    if not deal:
        conn.close()
        raise ValueError(f"Deal {deal_id} not found.")

    real_deal_id = deal['id']
    cur.execute("DELETE FROM brokerage_ledger WHERE deal_id = ?", (real_deal_id,))
    cur.execute("DELETE FROM dispatch_logs WHERE deal_id = ?", (real_deal_id,))
    cur.execute("DELETE FROM deals WHERE id = ?", (real_deal_id,))

    log_audit(conn, "deals", real_deal_id, "PERMANENT_DELETE", actor_name, actor_role, None, None, "Permanently purged from database")

    conn.commit()
    conn.close()
    return {'deal_id': real_deal_id, 'purged': True}

def bulk_soft_delete_deals(deal_ids: List[str], actor_name: str, actor_role: str, db_path: str = None) -> Dict[str, Any]:
    """Soft-deletes multiple deals into the Recycle Bin."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    deleted_ids = []
    now_iso = datetime.now().isoformat()

    for did in deal_ids:
        cur.execute("SELECT id, bgn_code FROM deals WHERE id = ? OR bgn_code = ?", (did, did))
        row = cur.fetchone()
        if row:
            real_id = row['id']
            cur.execute("UPDATE deals SET is_deleted = 1, deleted_at = ?, updated_at = ? WHERE id = ?", (now_iso, now_iso, real_id))
            log_audit(conn, "deals", real_id, "TRASH", actor_name, actor_role, {"is_deleted": 0}, {"is_deleted": 1, "deleted_at": now_iso}, "Bulk soft deleted")
            deleted_ids.append(real_id)

    conn.commit()
    conn.close()
    return {'count': len(deleted_ids), 'deleted_count': len(deleted_ids), 'deleted_ids': deleted_ids}

def bulk_restore_deals(deal_ids: List[str], actor_name: str, actor_role: str, db_path: str = None) -> Dict[str, Any]:
    """Restores multiple soft-deleted deals from the Recycle Bin."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    restored_ids = []
    now_iso = datetime.now().isoformat()

    for did in deal_ids:
        cur.execute("SELECT id, bgn_code FROM deals WHERE id = ? OR bgn_code = ?", (did, did))
        row = cur.fetchone()
        if row:
            real_id = row['id']
            cur.execute("UPDATE deals SET is_deleted = 0, deleted_at = NULL, updated_at = ? WHERE id = ?", (now_iso, real_id))
            log_audit(conn, "deals", real_id, "RESTORE", actor_name, actor_role, {"is_deleted": 1}, {"is_deleted": 0}, "Bulk restored from trash")
            restored_ids.append(real_id)

    conn.commit()
    conn.close()
    return {'count': len(restored_ids), 'restored_count': len(restored_ids), 'restored_ids': restored_ids}

def update_deal(deal_id: str, data: Dict[str, Any], actor_name: str = "Broker User", actor_role: str = "BROKER", db_path: str = None) -> Dict[str, Any]:
    """
    Updates an existing Bargain Deal in place.
    Preserves exact same Bargain ID without creating duplicates.
    Maintains rate confidentiality and marks reconfirmation required on commercial changes.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT * FROM deals WHERE id = ? OR bgn_code = ?", (deal_id, deal_id))
    deal = cur.fetchone()
    if not deal:
        conn.close()
        raise ValueError(f"Deal {deal_id} not found.")

    real_id = deal['id']
    old_deal = dict(deal)

    deal_date = data.get('deal_date') or old_deal['deal_date']
    seller_id = data.get('seller_id') or old_deal['seller_id']
    buyer_id = data.get('buyer_id') or old_deal['buyer_id']
    product_id = data.get('product_id') or old_deal['product_id']
    qty_qtl = float(data.get('quantity_qtl') if data.get('quantity_qtl') is not None else old_deal['quantity_qtl'])
    
    # Dual-Rate resolution
    old_seller_rate = float(old_deal.get('seller_rate') or old_deal.get('rate_per_qtl') or 0.0)
    old_buyer_rate = float(old_deal.get('buyer_rate') or old_deal.get('rate_per_qtl') or old_seller_rate)

    seller_rate = float(data.get('seller_rate') if data.get('seller_rate') is not None else (data.get('rate_per_qtl') if data.get('rate_per_qtl') is not None else old_seller_rate))
    buyer_rate = float(data.get('buyer_rate') if data.get('buyer_rate') is not None else (seller_rate if 'seller_rate' in data and 'buyer_rate' not in data else old_buyer_rate))
    if seller_rate <= 0:
        seller_rate = old_seller_rate
    if buyer_rate <= 0:
        buyer_rate = seller_rate
    rate_per_qtl = seller_rate

    qty_tonnes = float(convert_quintals_to_tonnes(qty_qtl))
    delivery_date = data.get('delivery_date') or old_deal.get('delivery_date') or deal_date
    advance_payment_date = data.get('advance_payment_date') or old_deal.get('advance_payment_date') or deal_date
    delivery_condition = data.get('delivery_condition') if data.get('delivery_condition') is not None else (old_deal.get('delivery_condition') or '')
    notes = data.get('notes') if data.get('notes') is not None else (old_deal.get('notes') or '')
    gst_applicable = int(data.get('gst_applicable', old_deal.get('gst_applicable', 1)))
    gst_percentage = float(data.get('gst_percentage', old_deal.get('gst_percentage', 5.0)))
    is_rate_inclusive = int(data.get('is_rate_inclusive_gst', old_deal.get('is_rate_inclusive_gst', 0)))

    # Commercial change detection
    significant_change = (
        old_deal['seller_id'] != seller_id or
        old_deal['buyer_id'] != buyer_id or
        old_deal['product_id'] != product_id or
        abs(float(old_deal['quantity_qtl']) - qty_qtl) > 0.001 or
        abs(old_seller_rate - seller_rate) > 0.001 or
        abs(old_buyer_rate - buyer_rate) > 0.001 or
        (old_deal.get('delivery_condition') or '') != delivery_condition or
        (old_deal.get('advance_payment_date') or '') != advance_payment_date
    )

    reconfirmation_required = int(old_deal.get('reconfirmation_required') or 0)
    new_status = data.get('status') or old_deal['status']

    if significant_change:
        reconfirmation_required = 1

    now_iso = datetime.now().isoformat()

    cur.execute("""
        UPDATE deals SET
            deal_date = ?,
            seller_id = ?,
            buyer_id = ?,
            product_id = ?,
            quantity_qtl = ?,
            quantity_tonnes = ?,
            rate_per_qtl = ?,
            seller_rate = ?,
            buyer_rate = ?,
            gst_applicable = ?,
            gst_percentage = ?,
            is_rate_inclusive_gst = ?,
            delivery_date = ?,
            advance_payment_date = ?,
            delivery_condition = ?,
            status = ?,
            reconfirmation_required = ?,
            notes = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        deal_date, seller_id, buyer_id, product_id,
        qty_qtl, qty_tonnes, rate_per_qtl, seller_rate, buyer_rate,
        gst_applicable, gst_percentage, is_rate_inclusive,
        delivery_date, advance_payment_date, delivery_condition,
        new_status, reconfirmation_required, notes,
        now_iso, real_id
    ))

    # If root deal of chain, update chain record
    if old_deal.get('link_sequence') == 1 and old_deal.get('chain_id'):
        cur.execute("""
            UPDATE deal_chains SET
                product_id = ?,
                initial_quantity_qtl = ?,
                remaining_unresold_quantity_qtl = ?,
                original_bill_seller_id = ?,
                final_bill_buyer_id = ?,
                final_billing_rate_qtl = ?,
                updated_at = ?
            WHERE id = ?
        """, (product_id, qty_qtl, qty_qtl, seller_id, buyer_id, buyer_rate, now_iso, old_deal['chain_id']))

    log_audit(conn, "deals", real_id, "UPDATE", actor_name, actor_role, old_deal, {
        "seller_rate": seller_rate,
        "buyer_rate": buyer_rate,
        "quantity_qtl": qty_qtl,
        "reconfirmation_required": reconfirmation_required,
        "status": new_status
    }, "Updated bargain terms")

    conn.commit()
    conn.close()

    return {
        'id': real_id,
        'bgn_code': old_deal.get('bgn_code') or real_id,
        'seller_rate': seller_rate,
        'buyer_rate': buyer_rate,
        'status': new_status,
        'reconfirmation_required': reconfirmation_required,
        'updated_at': now_iso
    }

def get_dispatch_logs(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Returns recent communication dispatch logs."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT l.*, COALESCE(d.bgn_code, d.id) AS bgn_code, d.deal_date, p.name AS product_name
        FROM dispatch_logs l
        JOIN deals d ON l.deal_id = d.id
        JOIN products p ON d.product_id = p.id
        ORDER BY l.created_at DESC
        LIMIT 50
    """)
    logs = [dict(r) for r in cur.fetchall()]
    conn.close()
    return logs

def create_dispatch_log(data: Dict[str, Any], actor_name: str = "Sanjay Kumar Aggarwal", db_path: str = DB_PATH) -> Dict[str, Any]:
    """Records a WhatsApp or Email dispatch event."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    log_id = f"DSP-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}"
    deal_id = data.get('deal_id')
    # Resolve deal_id if bgn_code was provided
    if deal_id:
        cur.execute("SELECT id FROM deals WHERE id = ? OR bgn_code = ?", (deal_id, deal_id))
        d_row = cur.fetchone()
        if d_row:
            deal_id = d_row['id']
    recipient_type = data.get('recipient_type', 'BUYER')
    if recipient_type not in ('BUYER', 'SELLER'):
        recipient_type = 'BUYER'
    recipient_name = data.get('recipient_name', 'Counterparty')
    channel = str(data.get('channel', 'WHATSAPP')).upper()
    if channel not in ('WHATSAPP', 'EMAIL'):
        channel = 'WHATSAPP'
    phone_or_email = data.get('phone_or_email', '')
    message_preview = data.get('message_preview', '')
    status = data.get('status', 'SENT')
    now_iso = datetime.now().isoformat()

    cur.execute("""
        INSERT INTO dispatch_logs (id, deal_id, recipient_type, recipient_name, channel, phone_or_email, message_preview, status, sent_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (log_id, deal_id, recipient_type, recipient_name, channel, phone_or_email, message_preview, status, actor_name, now_iso))

    conn.commit()
    conn.close()
    return {
        'id': log_id,
        'deal_id': deal_id,
        'recipient_name': recipient_name,
        'channel': channel,
        'status': status,
        'created_at': now_iso
    }
