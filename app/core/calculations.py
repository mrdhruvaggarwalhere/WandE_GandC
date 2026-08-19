"""
Calculation engine for G&C Deal and Brokerage Automation Platform.
Implements exact decimal arithmetic for all financial and quantity computations.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional, List

# Standard decimal quantizer for Indian Currency (2 decimal places)
DECIMAL_PLACES_CURRENCY = Decimal('0.01')
DECIMAL_PLACES_QTY = Decimal('0.0001')
DECIMAL_PLACES_RATE = Decimal('0.01')

def to_decimal(value: Any, default: str = '0') -> Decimal:
    """Safely convert any value to Decimal."""
    if value is None or value == '':
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value).strip().replace(',', ''))

def round_currency(val: Decimal) -> Decimal:
    return val.quantize(DECIMAL_PLACES_CURRENCY, rounding=ROUND_HALF_UP)

def round_qty(val: Decimal) -> Decimal:
    return val.quantize(DECIMAL_PLACES_QTY, rounding=ROUND_HALF_UP)

def format_qty_clean(qty: Decimal) -> str:
    """Formats quantity without ugly trailing .0 if integer."""
    if qty == qty.to_integral():
        return f"{int(qty)}"
    return f"{qty:g}"

def convert_quintals_to_tonnes(qty_quintals: Any) -> Decimal:
    """
    1 Metric Tonne = 1,000 kg = 10 Quintals.
    quantity_in_tonnes = quantity_in_quintals / 10
    """
    q = to_decimal(qty_quintals)
    return round_qty(q / Decimal('10'))

def convert_tonnes_to_quintals(qty_tonnes: Any) -> Decimal:
    """
    quantity_in_quintals = quantity_in_tonnes * 10
    """
    t = to_decimal(qty_tonnes)
    return round_qty(t * Decimal('10'))

def calculate_price_difference(
    actual_sale_rate_per_qtl: Any,
    party_authorized_rate_per_qtl: Any,
    quantity_in_quintals: Any
) -> Dict[str, Any]:
    """
    price_difference_per_quintal = actual_sale_rate_per_quintal - party_authorized_rate_per_quintal
    price_difference_profit = price_difference_per_quintal * quantity_in_quintals
    
    Supports positive, zero, and negative results (losses).
    """
    actual_rate = to_decimal(actual_sale_rate_per_qtl)
    auth_rate = to_decimal(party_authorized_rate_per_qtl)
    qty_qtl = to_decimal(quantity_in_quintals)

    diff_per_qtl = actual_rate - auth_rate
    profit = diff_per_qtl * qty_qtl

    return {
        'actual_rate_per_qtl': actual_rate,
        'authorized_rate_per_qtl': auth_rate,
        'quantity_qtl': qty_qtl,
        'price_diff_per_qtl': diff_per_qtl,
        'price_diff_profit': round_currency(profit),
        'is_profit': profit > Decimal('0'),
        'is_loss': profit < Decimal('0'),
        'is_even': profit == Decimal('0'),
    }

def calculate_brokerage(
    quantity_in_tonnes: Any,
    buyer_brokerage_rate_per_tonne: Any,
    seller_brokerage_rate_per_tonne: Any,
    buyer_brokerage_enabled: bool = True,
    seller_brokerage_enabled: bool = True
) -> Dict[str, Any]:
    """
    buyer_brokerage = quantity_in_tonnes * buyer_brokerage_rate_per_tonne
    seller_brokerage = quantity_in_tonnes * seller_brokerage_rate_per_tonne
    deal_brokerage = buyer_brokerage + seller_brokerage
    """
    qty_t = to_decimal(quantity_in_tonnes)
    b_rate = to_decimal(buyer_brokerage_rate_per_tonne) if buyer_brokerage_enabled else Decimal('0')
    s_rate = to_decimal(seller_brokerage_rate_per_tonne) if seller_brokerage_enabled else Decimal('0')

    buyer_brokerage = round_currency(qty_t * b_rate)
    seller_brokerage = round_currency(qty_t * s_rate)
    total_brokerage = buyer_brokerage + seller_brokerage

    return {
        'quantity_tonnes': qty_t,
        'buyer_rate_per_tonne': b_rate,
        'seller_rate_per_tonne': s_rate,
        'buyer_brokerage': buyer_brokerage,
        'seller_brokerage': seller_brokerage,
        'total_brokerage': total_brokerage,
    }

def calculate_taxable_and_gst(
    quantity_in_quintals: Any,
    rate_per_quintal: Any,
    gst_applicable: bool = True,
    gst_percentage: Any = Decimal('5.0'),
    is_rate_inclusive: bool = False
) -> Dict[str, Any]:
    """
    Calculates taxable value, GST amount, and total invoice value.
    """
    qty = to_decimal(quantity_in_quintals)
    rate = to_decimal(rate_per_quintal)
    gst_pct = to_decimal(gst_percentage) if gst_applicable else Decimal('0')

    if not gst_applicable or gst_pct == Decimal('0'):
        taxable_value = round_currency(qty * rate)
        gst_amount = Decimal('0.00')
        total_value = taxable_value
    elif is_rate_inclusive:
        total_value = round_currency(qty * rate)
        taxable_value = round_currency(total_value / (Decimal('1') + (gst_pct / Decimal('100'))))
        gst_amount = round_currency(total_value - taxable_value)
    else:
        taxable_value = round_currency(qty * rate)
        gst_amount = round_currency(taxable_value * (gst_pct / Decimal('100')))
        total_value = round_currency(taxable_value + gst_amount)

    return {
        'quantity_qtl': qty,
        'rate_per_qtl': rate,
        'gst_applicable': gst_applicable,
        'gst_percentage': gst_pct,
        'is_rate_inclusive': is_rate_inclusive,
        'taxable_value': taxable_value,
        'gst_amount': gst_amount,
        'total_value': total_value,
    }

def calculate_deal_chain_summary(deals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Summarizes a complete deal chain:
    - Original Bill Seller: Seller in the first deal
    - Final Bill Buyer: Buyer in the latest completed deal
    - Total Price Difference Profit: Sum of price difference profit across all resale links
    - Total Brokerage: Sum of buyer and seller brokerage across all deals
    - Total Earning: Total Price Difference + Total Brokerage
    - Direct Billing Text
    """
    if not deals:
        return {
            'total_deals': 0,
            'total_price_diff_profit': Decimal('0.00'),
            'total_buyer_brokerage': Decimal('0.00'),
            'total_seller_brokerage': Decimal('0.00'),
            'total_brokerage': Decimal('0.00'),
            'total_earning': Decimal('0.00'),
            'original_bill_seller': None,
            'final_bill_buyer': None,
            'final_rate_per_qtl': Decimal('0.00'),
            'final_quantity_qtl': Decimal('0.00'),
            'direct_billing_instruction': '',
        }

    # Filter active/completed deals (skip cancelled)
    active_deals = [d for d in deals if d.get('status') != 'CANCELLED']
    if not active_deals:
        active_deals = deals

    first_deal = active_deals[0]
    last_deal = active_deals[-1]

    original_bill_seller = first_deal.get('seller_name') or first_deal.get('seller_id')
    final_bill_buyer = last_deal.get('buyer_name') or last_deal.get('buyer_id')
    product_name = last_deal.get('product_name') or 'M.OIL'
    final_quantity_qtl = to_decimal(last_deal.get('quantity_qtl', 0))
    final_rate_per_qtl = to_decimal(last_deal.get('rate_per_qtl', 0))
    gst_note = '+ GST' if last_deal.get('gst_applicable', True) else '(No GST)'

    total_price_diff_profit = Decimal('0.00')
    total_buyer_brokerage = Decimal('0.00')
    total_seller_brokerage = Decimal('0.00')

    for d in active_deals:
        p_profit = to_decimal(d.get('price_diff_profit', 0))
        total_price_diff_profit += p_profit

        b_brok = to_decimal(d.get('buyer_brokerage_amount', 0))
        s_brok = to_decimal(d.get('seller_brokerage_amount', 0))
        total_buyer_brokerage += b_brok
        total_seller_brokerage += s_brok

    total_brokerage = total_buyer_brokerage + total_seller_brokerage
    total_earning = total_price_diff_profit + total_brokerage

    qty_str = format_qty_clean(final_quantity_qtl)

    instruction_text = (
        f"{original_bill_seller} will issue a direct bill to {final_bill_buyer} "
        f"for {qty_str} quintals of {product_name} at "
        f"₹{final_rate_per_qtl:,.2f} {gst_note} per quintal."
    )

    return {
        'total_deals': len(active_deals),
        'original_bill_seller': original_bill_seller,
        'final_bill_buyer': final_bill_buyer,
        'product_name': product_name,
        'final_quantity_qtl': final_quantity_qtl,
        'final_quantity_tonnes': convert_quintals_to_tonnes(final_quantity_qtl),
        'final_rate_per_qtl': final_rate_per_qtl,
        'total_price_diff_profit': round_currency(total_price_diff_profit),
        'total_buyer_brokerage': round_currency(total_buyer_brokerage),
        'total_seller_brokerage': round_currency(total_seller_brokerage),
        'total_brokerage': round_currency(total_brokerage),
        'total_earning': round_currency(total_earning),
        'direct_billing_instruction': instruction_text,
    }
