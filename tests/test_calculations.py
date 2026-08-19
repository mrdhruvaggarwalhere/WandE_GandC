"""
Unit tests for core financial and mathematical calculation engines.
"""

from decimal import Decimal
import pytest
from app.core.calculations import (
    convert_quintals_to_tonnes,
    convert_tonnes_to_quintals,
    calculate_price_difference,
    calculate_brokerage,
    calculate_taxable_and_gst,
    calculate_deal_chain_summary,
    to_decimal
)

def test_unit_conversions():
    # 320 Quintals = 32 MT
    assert convert_quintals_to_tonnes(320) == Decimal('32.0000')
    assert convert_tonnes_to_quintals(32) == Decimal('320.0000')
    
    # 15 Quintals = 1.5 MT
    assert convert_quintals_to_tonnes(15) == Decimal('1.5000')
    assert convert_tonnes_to_quintals(Decimal('1.5')) == Decimal('15.0000')

def test_price_difference_positive_profit():
    # Sold @ 16475, Auth @ 16450, Qty = 320 -> Profit = ₹8,000
    res = calculate_price_difference(16475, 16450, 320)
    assert res['price_diff_per_qtl'] == Decimal('25.00')
    assert res['price_diff_profit'] == Decimal('8000.00')
    assert res['is_profit'] is True
    assert res['is_loss'] is False

def test_price_difference_loss():
    # Sold @ 16400, Auth @ 16450, Qty = 320 -> Loss = -₹16,000
    res = calculate_price_difference(16400, 16450, 320)
    assert res['price_diff_per_qtl'] == Decimal('-50.00')
    assert res['price_diff_profit'] == Decimal('-16000.00')
    assert res['is_profit'] is False
    assert res['is_loss'] is True

def test_price_difference_zero():
    res = calculate_price_difference(16500, 16500, 100)
    assert res['price_diff_per_qtl'] == Decimal('0.00')
    assert res['price_diff_profit'] == Decimal('0.00')
    assert res['is_even'] is True

def test_brokerage_calculations():
    # 32 MT, Buyer @ 50/MT, Seller @ 50/MT -> Buyer = 1600, Seller = 1600, Total = 3200
    res = calculate_brokerage(32, 50, 50)
    assert res['buyer_brokerage'] == Decimal('1600.00')
    assert res['seller_brokerage'] == Decimal('1600.00')
    assert res['total_brokerage'] == Decimal('3200.00')

def test_brokerage_different_rates_and_zero():
    # Buyer @ 40/MT, Seller @ 0 (Waived/Disabled) -> Total = 1280
    res = calculate_brokerage(32, 40, 0)
    assert res['buyer_brokerage'] == Decimal('1280.00')
    assert res['seller_brokerage'] == Decimal('0.00')
    assert res['total_brokerage'] == Decimal('1280.00')

def test_gst_calculations():
    # 320 Qtl @ 15700, 5% GST
    res = calculate_taxable_and_gst(320, 15700, True, 5.0)
    assert res['taxable_value'] == Decimal('5024000.00')
    assert res['gst_amount'] == Decimal('251200.00')
    assert res['total_value'] == Decimal('5275200.00')
