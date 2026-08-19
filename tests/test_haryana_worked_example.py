"""
Integration test for the mandatory Haryana Industries -> Nagpal -> M.L. Nagpal -> Shakti Nutritions worked example.
"""

from decimal import Decimal
import pytest
from app.core.database import init_db, get_db_connection
from app.core.seed_data import seed_all
from app.core.calculations import (
    convert_quintals_to_tonnes,
    calculate_price_difference,
    calculate_brokerage,
    calculate_deal_chain_summary
)
import app.api.routes as api_routes

def test_haryana_to_shakti_acceptance_scenario():
    # 1. Initialize clean database with seed data
    init_db()
    seed_all()

    # 2. Fetch Deal Chain LOT-2026-001
    chain_details = api_routes.get_deal_chain_details("LOT-2026-001")
    chain = chain_details['chain']
    deals = chain_details['deals']
    summary = chain_details['summary']
    billing_instruction = chain_details['billing_instruction']

    # Verify 3 deals exist in the chain
    assert len(deals) == 3

    # Deal 1: Initial Purchase
    d1 = deals[0]
    assert d1['seller_id'] == 'PTY-002' # Nagpal Enterprises
    assert d1['buyer_id'] == 'PTY-001'  # Haryana Industries
    assert d1['quantity_qtl'] == 320.0
    assert d1['quantity_tonnes'] == 32.0
    assert d1['rate_per_qtl'] == 15700.0
    assert d1['price_diff_profit'] == 0.0 # Root purchase has no resale profit

    # Deal 2: First Resale Link
    d2 = deals[1]
    assert d2['seller_id'] == 'PTY-001' # Haryana Industries (instructing)
    assert d2['buyer_id'] == 'PTY-003'  # M.L. Nagpal Industries
    assert d2['authorized_selling_rate_qtl'] == 16450.0
    assert d2['rate_per_qtl'] == 16475.0
    assert d2['price_diff_per_qtl'] == 25.0
    assert d2['price_diff_profit'] == 8000.0 # ₹25 * 320 = ₹8,000

    # Deal 3: Second Resale Link
    d3 = deals[2]
    assert d3['seller_id'] == 'PTY-003' # M.L. Nagpal Industries (instructing)
    assert d3['buyer_id'] == 'PTY-004'  # Shakti Nutritions Pvt. Ltd.
    assert d3['authorized_selling_rate_qtl'] == 16475.0
    assert d3['rate_per_qtl'] == 16700.0
    assert d3['price_diff_per_qtl'] == 225.0
    assert d3['price_diff_profit'] == 72000.0 # ₹225 * 320 = ₹72,000

    # Summary Assertions
    assert summary['total_price_diff_profit'] == Decimal('80000.00') # ₹8,000 + ₹72,000 = ₹80,000
    assert summary['original_bill_seller'] == 'NAGPAL ENTERPRISES PVT. LTD., ANOUPGARH'
    assert summary['final_bill_buyer'] == 'SHAKTI NUTRITIONS PVT. LTD.'
    assert summary['final_rate_per_qtl'] == Decimal('16700.00')
    assert summary['final_quantity_qtl'] == Decimal('320.00')

    # Direct Billing Instruction Text
    expected_text = "NAGPAL ENTERPRISES PVT. LTD., ANOUPGARH will issue a direct bill to SHAKTI NUTRITIONS PVT. LTD. for 320 quintals of M.OIL at ₹16,700.00 + GST per quintal."
    assert summary['direct_billing_instruction'] == expected_text
    assert billing_instruction['instruction_text'] == expected_text
    assert billing_instruction['approval_status'] == 'APPROVED'
