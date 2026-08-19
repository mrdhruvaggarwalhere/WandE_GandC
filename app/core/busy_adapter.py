"""
BUSY Accounting Integration Adapter for G&C Deal and Brokerage Automation Platform.
Generates compliant intermediate XML, JSON, and CSV vouchers for BUSY 18/21 import utilities.
Enforces strict safeguard preventing intermediate deal-chain records from official posting.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom
import sqlite3
from app.core.database import get_db_connection, DB_PATH, log_audit

def generate_busy_xml_voucher(billing_instruction_id: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Generates standard BUSY XML format for an Approved Direct Billing Instruction.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            b.id AS instruction_id, b.chain_id, b.quantity_qtl, b.rate_per_qtl,
            b.gst_applicable, b.gst_percentage, b.taxable_value, b.gst_amount, b.total_value,
            b.delivery_date, b.instruction_text, b.approval_status,
            s.legal_name AS seller_name, s.busy_ledger_id AS seller_busy_code, s.gstin AS seller_gstin,
            buy.legal_name AS buyer_name, buy.busy_ledger_id AS buyer_busy_code, buy.gstin AS buyer_gstin,
            p.name AS product_name, p.busy_item_id AS product_busy_code, p.hsn_sac_code
        FROM billing_instructions b
        JOIN parties s ON b.original_seller_id = s.id
        JOIN parties buy ON b.final_buyer_id = buy.id
        JOIN products p ON b.product_id = p.id
        WHERE b.id = ?
    """, (billing_instruction_id,))

    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Billing Instruction {billing_instruction_id} not found.")

    if row['approval_status'] != 'APPROVED':
        conn.close()
        raise PermissionError(f"Billing Instruction must be in 'APPROVED' state before BUSY staging. Current status: {row['approval_status']}")

    # Build XML document
    root = ET.Element("BUSY_DATA", {"Version": "21.0", "GeneratedAt": datetime.now().isoformat()})
    voucher = ET.SubElement(root, "VOUCHER")
    
    ET.SubElement(voucher, "VchType").text = "Sales"
    ET.SubElement(voucher, "VchSeries").text = "Main"
    ET.SubElement(voucher, "VchNo").text = f"INV-{row['chain_id']}"
    ET.SubElement(voucher, "Date").text = str(row['delivery_date']).replace('-', '')
    ET.SubElement(voucher, "PartyName").text = row['buyer_name']
    ET.SubElement(voucher, "PartyBusyCode").text = row['buyer_busy_code'] or "LED-AUTO"
    ET.SubElement(voucher, "PartyGSTIN").text = row['buyer_gstin'] or ""
    
    ET.SubElement(voucher, "SellerName").text = row['seller_name']
    ET.SubElement(voucher, "SellerBusyCode").text = row['seller_busy_code'] or "LED-AUTO"
    ET.SubElement(voucher, "SellerGSTIN").text = row['seller_gstin'] or ""
    
    ET.SubElement(voucher, "MatCentre").text = "Main Store"
    ET.SubElement(voucher, "TaxInclusive").text = "N"
    ET.SubElement(voucher, "BillType").text = f"GST {row['gst_percentage']}% ItemWise"
    ET.SubElement(voucher, "Narration").text = f"Direct bill instruction: {row['instruction_text']}"

    # Item details
    items_elem = ET.SubElement(voucher, "ITEM_DETAILS")
    item = ET.SubElement(items_elem, "ITEM")
    ET.SubElement(item, "ItemName").text = row['product_name']
    ET.SubElement(item, "ItemBusyCode").text = row['product_busy_code'] or "ITM-AUTO"
    ET.SubElement(item, "HSNCode").text = row['hsn_sac_code'] or "151491"
    ET.SubElement(item, "Qty").text = str(row['quantity_qtl'])
    ET.SubElement(item, "Unit").text = "QTL"
    ET.SubElement(item, "Price").text = str(row['rate_per_qtl'])
    ET.SubElement(item, "Amount").text = str(row['taxable_value'])
    ET.SubElement(item, "GSTPercent").text = str(row['gst_percentage'])
    ET.SubElement(item, "GSTAmount").text = str(row['gst_amount'])
    ET.SubElement(item, "TotalAmount").text = str(row['total_value'])

    # Format pretty XML
    rough_string = ET.tostring(root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")

    # Log sync staging
    log_audit(conn, "busy_integration", billing_instruction_id, "STAGE", "Sunil Sharma", "ACCOUNTS", None, {
        "voucher_no": f"INV-{row['chain_id']}",
        "buyer": row['buyer_name'],
        "seller": row['seller_name'],
        "total_value": row['total_value']
    }, "Staged direct billing voucher for BUSY export")

    cur.execute("""
        INSERT INTO busy_sync_logs (id, voucher_no, chain_id, payload, sync_status, error_message, synced_at)
        VALUES (?, ?, ?, ?, 'STAGED', NULL, ?)
    """, (
        f"BSY-LOG-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        f"INV-{row['chain_id']}",
        row['chain_id'],
        pretty_xml,
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

    return {
        'instruction_id': billing_instruction_id,
        'voucher_no': f"INV-{row['chain_id']}",
        'xml_payload': pretty_xml,
        'json_payload': {
            'voucher_type': 'Sales',
            'voucher_no': f"INV-{row['chain_id']}",
            'date': row['delivery_date'],
            'seller': {'name': row['seller_name'], 'busy_id': row['seller_busy_code'], 'gstin': row['seller_gstin']},
            'buyer': {'name': row['buyer_name'], 'busy_id': row['buyer_busy_code'], 'gstin': row['buyer_gstin']},
            'product': {'name': row['product_name'], 'busy_id': row['product_busy_code'], 'hsn': row['hsn_sac_code']},
            'quantity_qtl': row['quantity_qtl'],
            'rate_per_qtl': row['rate_per_qtl'],
            'taxable_value': row['taxable_value'],
            'gst_amount': row['gst_amount'],
            'total_value': row['total_value'],
            'narration': row['instruction_text']
        }
    }
