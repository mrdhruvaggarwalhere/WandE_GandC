"""
Excel export engine for G&C Deal and Brokerage Automation Platform.
Implements OpenPyXL styled multi-sheet workbook generation with strict Columns A:G mapping compliance.
"""

import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
from typing import Dict, Any, List, Optional
import sqlite3
from app.core.database import get_db_connection, DB_PATH, log_audit

# Modern Corporate Palette for Excel Sheets
HEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid") # Slate-900
HEADER_FONT = Font(name="Arial", size=10, bold=True, color="FFFFFF")

ACCENT_FILL = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid") # Teal-700
ACCENT_FONT = Font(name="Arial", size=10, bold=True, color="FFFFFF")

ALERT_FILL = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid") # Amber-100
PROFIT_FILL = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid") # Emerald-100
LOSS_FILL = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid") # Red-100

THIN_BORDER = Border(
    left=Side(style='thin', color='E2E8F0'),
    right=Side(style='thin', color='E2E8F0'),
    top=Side(style='thin', color='E2E8F0'),
    bottom=Side(style='thin', color='E2E8F0')
)

def format_date_str(date_val: Optional[str]) -> str:
    if not date_val:
        return ""
    try:
        # ISO string YYYY-MM-DD to DD/MM/YYYY
        parts = str(date_val).split('T')[0].split('-')
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except Exception:
        pass
    return str(date_val)

def generate_full_excel_workbook(db_path: str = DB_PATH, filters: Optional[Dict[str, Any]] = None) -> bytes:
    """
    Generates a full formatted Excel workbook containing all 8 operational sheets.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    wb = openpyxl.Workbook()
    # Remove default sheet
    default_sheet = wb.active
    wb.remove(default_sheet)

    # -------------------------------------------------------------
    # Sheet 1: Deals (A:G Mapping + Extended Fields)
    # -------------------------------------------------------------
    ws_deals = wb.create_sheet(title="Deals (A-G Mapping)")
    ws_deals.views.sheetView[0].showGridLines = True

    deals_headers = [
        # Mandatory A:G Columns
        "Deal Date (A)", "Buyer (B)", "Seller (C)", "Product (D)", "Quantity (E)", "Price and GST (F)", "Delivery Date (G)",
        # Extended Analytical Columns
        "Deal ID (H)", "Lot / Chain ID (I)", "Link Seq (J)", "Qty (Quintals)", "Qty (Tonnes)",
        "Rate / Qtl (₹)", "Auth Rate / Qtl (₹)", "Rate Diff / Qtl (₹)", "Price Diff Profit (₹)",
        "Buyer Brokerage Rate (₹/T)", "Buyer Brokerage (₹)", "Seller Brokerage Rate (₹/T)", "Seller Brokerage (₹)",
        "Total Deal Brokerage (₹)", "Total Deal Earning (₹)", "GST %", "Taxable Value (₹)", "GST Amount (₹)", "Total Value (₹)",
        "Orig Bill Seller", "Final Bill Buyer", "Status", "Delivery Status", "Notes", "Created By", "Created At"
    ]

    ws_deals.append(deals_headers)

    # Fetch Deals with joined party and product names
    query = """
        SELECT 
            d.deal_date, b.legal_name AS buyer_name, s.legal_name AS seller_name,
            p.name AS product_name, d.quantity_qtl, d.quantity_tonnes, d.rate_per_qtl,
            d.authorized_selling_rate_qtl, d.gst_applicable, d.gst_percentage,
            d.is_rate_inclusive_gst, d.delivery_date, d.id AS deal_id, d.chain_id,
            d.link_sequence, d.buyer_brokerage_rate_per_tonne, d.seller_brokerage_rate_per_tonne,
            d.buyer_brokerage_amount, d.seller_brokerage_amount, d.total_brokerage_amount,
            d.price_diff_per_qtl, d.price_diff_profit, d.delivery_status, d.status,
            d.notes, d.created_by, d.created_at,
            c.original_bill_seller_id, obs.legal_name AS orig_seller_name,
            c.final_bill_buyer_id, fbb.legal_name AS final_buyer_name
        FROM deals d
        JOIN parties b ON d.buyer_id = b.id
        JOIN parties s ON d.seller_id = s.id
        JOIN products p ON d.product_id = p.id
        JOIN deal_chains c ON d.chain_id = c.id
        JOIN parties obs ON c.original_bill_seller_id = obs.id
        LEFT JOIN parties fbb ON c.final_bill_buyer_id = fbb.id
        ORDER BY d.deal_date ASC, d.id ASC
    """
    cur.execute(query)
    deal_rows = cur.fetchall()

    for r in deal_rows:
        # Col E: Quantity formatted
        qty_display = f"{r['quantity_qtl']:g} Qtl ({r['quantity_tonnes']:g} MT)"
        
        # Col F: Price and GST formatted (e.g. "16475+GST")
        gst_suffix = f"+{r['gst_percentage']:g}% GST" if r['gst_applicable'] else "(No GST)"
        price_gst_display = f"₹{r['rate_per_qtl']:,.2f} {gst_suffix}"

        # Taxable & GST calculation for row
        taxable_val = r['quantity_qtl'] * r['rate_per_qtl']
        gst_amt = taxable_val * (r['gst_percentage'] / 100.0) if r['gst_applicable'] else 0.0
        total_val = taxable_val + gst_amt

        deal_earning = r['price_diff_profit'] + r['total_brokerage_amount']

        row_data = [
            format_date_str(r['deal_date']), # A
            r['buyer_name'],                  # B
            r['seller_name'],                 # C
            r['product_name'],                # D
            qty_display,                      # E
            price_gst_display,                # F
            format_date_str(r['delivery_date']), # G
            r['deal_id'],                     # H
            r['chain_id'],                    # I
            r['link_sequence'],               # J
            r['quantity_qtl'],                # K
            r['quantity_tonnes'],             # L
            r['rate_per_qtl'],                # M
            r['authorized_selling_rate_qtl'], # N
            r['price_diff_per_qtl'],          # O
            r['price_diff_profit'],           # P
            r['buyer_brokerage_rate_per_tonne'], # Q
            r['buyer_brokerage_amount'],      # R
            r['seller_brokerage_rate_per_tonne'], # S
            r['seller_brokerage_amount'],     # T
            r['total_brokerage_amount'],      # U
            deal_earning,                     # V
            f"{r['gst_percentage']}%",        # W
            taxable_val,                      # X
            gst_amt,                          # Y
            total_val,                        # Z
            r['orig_seller_name'],            # AA
            r['final_buyer_name'] or 'Pending', # AB
            r['status'],                      # AC
            r['delivery_status'],             # AD
            r['notes'] or '',                 # AE
            r['created_by'],                  # AF
            format_date_str(r['created_at'])  # AG
        ]
        ws_deals.append(row_data)

    # -------------------------------------------------------------
    # Sheet 2: Deal Chains (Lots)
    # -------------------------------------------------------------
    ws_chains = wb.create_sheet(title="Deal Chains (Lots)")
    ws_chains.views.sheetView[0].showGridLines = True
    chain_headers = [
        "Lot / Chain ID", "Product", "Initial Qtl", "Initial Tonnes", "Remaining Qtl",
        "Original Bill Seller", "Final Bill Buyer", "Final Rate (₹/Qtl)", "Status",
        "Approval Status", "Total Diff Profit (₹)", "Total Brokerage (₹)", "Total Earning (₹)", "Created Date"
    ]
    ws_chains.append(chain_headers)

    cur.execute("""
        SELECT 
            c.id, p.name AS product_name, c.initial_quantity_qtl, c.remaining_unresold_quantity_qtl,
            obs.legal_name AS orig_seller, fbb.legal_name AS final_buyer,
            c.final_billing_rate_qtl, c.status, c.approval_status, c.created_at,
            COALESCE(SUM(d.price_diff_profit), 0) AS total_diff_profit,
            COALESCE(SUM(d.total_brokerage_amount), 0) AS total_brokerage
        FROM deal_chains c
        JOIN products p ON c.product_id = p.id
        JOIN parties obs ON c.original_bill_seller_id = obs.id
        LEFT JOIN parties fbb ON c.final_bill_buyer_id = fbb.id
        LEFT JOIN deals d ON c.id = d.chain_id AND d.status != 'CANCELLED'
        GROUP BY c.id
        ORDER BY c.created_at DESC
    """)
    for c_row in cur.fetchall():
        init_t = c_row['initial_quantity_qtl'] / 10.0
        tot_earn = c_row['total_diff_profit'] + c_row['total_brokerage']
        ws_chains.append([
            c_row['id'], c_row['product_name'], c_row['initial_quantity_qtl'], init_t,
            c_row['remaining_unresold_quantity_qtl'], c_row['orig_seller'],
            c_row['final_buyer'] or 'Awaiting Resale', c_row['final_billing_rate_qtl'] or 0.0,
            c_row['status'], c_row['approval_status'], c_row['total_diff_profit'],
            c_row['total_brokerage'], tot_earn, format_date_str(c_row['created_at'])
        ])

    # -------------------------------------------------------------
    # Sheet 3: Official Billing Instructions
    # -------------------------------------------------------------
    ws_billing = wb.create_sheet(title="Billing Instructions")
    ws_billing.views.sheetView[0].showGridLines = True
    billing_headers = [
        "Instruction ID", "Chain ID", "Original Bill Seller", "Final Bill Buyer", "Product",
        "Bill Qty (Qtl)", "Bill Qty (Tonnes)", "Final Rate (₹/Qtl)", "GST %", "Taxable Value (₹)",
        "GST Amount (₹)", "Total Value (₹)", "Delivery Date", "Official Instruction",
        "Approval Status", "Approved By", "Approved At", "Remarks"
    ]
    ws_billing.append(billing_headers)

    cur.execute("""
        SELECT 
            b.id, b.chain_id, s.legal_name AS seller_name, buy.legal_name AS buyer_name,
            p.name AS product_name, b.quantity_qtl, b.rate_per_qtl, b.gst_percentage,
            b.taxable_value, b.gst_amount, b.total_value, b.delivery_date,
            b.instruction_text, b.approval_status, b.approved_by, b.approved_at, b.remarks
        FROM billing_instructions b
        JOIN parties s ON b.original_seller_id = s.id
        JOIN parties buy ON b.final_buyer_id = buy.id
        JOIN products p ON b.product_id = p.id
        ORDER BY b.created_at DESC
    """)
    for b_row in cur.fetchall():
        ws_billing.append([
            b_row['id'], b_row['chain_id'], b_row['seller_name'], b_row['buyer_name'],
            b_row['product_name'], b_row['quantity_qtl'], b_row['quantity_qtl'] / 10.0,
            b_row['rate_per_qtl'], f"{b_row['gst_percentage']}%", b_row['taxable_value'],
            b_row['gst_amount'], b_row['total_value'], format_date_str(b_row['delivery_date']),
            b_row['instruction_text'], b_row['approval_status'], b_row['approved_by'] or '',
            format_date_str(b_row['approved_at']), b_row['remarks'] or ''
        ])

    # -------------------------------------------------------------
    # Sheet 4: Brokerage Breakdown
    # -------------------------------------------------------------
    ws_brok = wb.create_sheet(title="Brokerage Detail")
    ws_brok.views.sheetView[0].showGridLines = True
    brok_headers = [
        "Deal ID", "Deal Date", "Buyer Party", "Buyer Qty (MT)", "Buyer Rate (₹/MT)", "Buyer Brokerage (₹)",
        "Seller Party", "Seller Qty (MT)", "Seller Rate (₹/MT)", "Seller Brokerage (₹)", "Total Deal Brokerage (₹)"
    ]
    ws_brok.append(brok_headers)

    cur.execute("""
        SELECT 
            d.id, d.deal_date, b.legal_name AS buyer_name, d.quantity_tonnes,
            d.buyer_brokerage_rate_per_tonne, d.buyer_brokerage_amount,
            s.legal_name AS seller_name, d.seller_brokerage_rate_per_tonne,
            d.seller_brokerage_amount, d.total_brokerage_amount
        FROM deals d
        JOIN parties b ON d.buyer_id = b.id
        JOIN parties s ON d.seller_id = s.id
        WHERE d.status != 'CANCELLED'
        ORDER BY d.deal_date ASC
    """)
    for br in cur.fetchall():
        ws_brok.append([
            br['id'], format_date_str(br['deal_date']), br['buyer_name'], br['quantity_tonnes'],
            br['buyer_brokerage_rate_per_tonne'], br['buyer_brokerage_amount'],
            br['seller_name'], br['quantity_tonnes'], br['seller_brokerage_rate_per_tonne'],
            br['seller_brokerage_amount'], br['total_brokerage_amount']
        ])

    # -------------------------------------------------------------
    # Sheet 5: Party Ledger & Dues
    # -------------------------------------------------------------
    ws_ledger = wb.create_sheet(title="Party Ledger & Dues")
    ws_ledger.views.sheetView[0].showGridLines = True
    ledger_headers = [
        "Entry ID", "Date", "Party Name", "Type", "Amount (₹)", "Reference / Deal", "Notes", "Recorded By"
    ]
    ws_ledger.append(ledger_headers)

    cur.execute("""
        SELECT 
            l.id, l.entry_date, p.legal_name AS party_name, l.entry_type,
            l.amount, l.reference_no, l.notes, l.created_by
        FROM brokerage_ledger l
        JOIN parties p ON l.party_id = p.id
        ORDER BY l.entry_date DESC, l.created_at DESC
    """)
    for lr in cur.fetchall():
        ws_ledger.append([
            lr['id'], format_date_str(lr['entry_date']), lr['party_name'], lr['entry_type'],
            lr['amount'], lr['reference_no'] or '', lr['notes'] or '', lr['created_by']
        ])

    # -------------------------------------------------------------
    # Sheet 6: Products Master
    # -------------------------------------------------------------
    ws_prod = wb.create_sheet(title="Products")
    ws_prod.views.sheetView[0].showGridLines = True
    prod_headers = ["Product ID", "Product Name", "Short Code", "Default Unit", "Ratio (Qtl/MT)", "Default GST %", "HSN Code", "BUSY Item Code", "Status"]
    ws_prod.append(prod_headers)
    cur.execute("SELECT id, name, short_code, default_unit, quintal_to_tonne_ratio, default_gst_rate, hsn_sac_code, busy_item_id, is_active FROM products")
    for pr in cur.fetchall():
        ws_prod.append([
            pr['id'], pr['name'], pr['short_code'], pr['default_unit'], pr['quintal_to_tonne_ratio'],
            f"{pr['default_gst_rate']}%", pr['hsn_sac_code'] or '', pr['busy_item_id'] or '',
            'Active' if pr['is_active'] else 'Inactive'
        ])

    # -------------------------------------------------------------
    # Sheet 7: Parties Master
    # -------------------------------------------------------------
    ws_party = wb.create_sheet(title="Parties")
    ws_party.views.sheetView[0].showGridLines = True
    party_headers = [
        "Party ID", "Legal Name", "Type", "City", "State", "Contact Person", "Phone", "GSTIN",
        "Default Buyer Rate (₹/T)", "Default Seller Rate (₹/T)", "Brokerage Enabled", "BUSY Ledger ID", "Status"
    ]
    ws_party.append(party_headers)
    cur.execute("SELECT id, legal_name, party_type, city, state, contact_person, phone, gstin, default_buyer_brokerage_per_tonne, default_seller_brokerage_per_tonne, brokerage_enabled, busy_ledger_id, is_active FROM parties")
    for pty in cur.fetchall():
        ws_party.append([
            pty['id'], pty['legal_name'], pty['party_type'], pty['city'] or '', pty['state'] or '',
            pty['contact_person'] or '', pty['phone'] or '', pty['gstin'] or '',
            pty['default_buyer_brokerage_per_tonne'], pty['default_seller_brokerage_per_tonne'],
            'Yes' if pty['brokerage_enabled'] else 'No', pty['busy_ledger_id'] or '',
            'Active' if pty['is_active'] else 'Inactive'
        ])

    # -------------------------------------------------------------
    # Sheet 8: Audit Log
    # -------------------------------------------------------------
    ws_audit = wb.create_sheet(title="Audit Log")
    ws_audit.views.sheetView[0].showGridLines = True
    audit_headers = ["Audit ID", "Timestamp", "Entity", "Entity ID", "Action", "User", "Role", "Reason"]
    ws_audit.append(audit_headers)
    cur.execute("SELECT id, created_at, entity_name, entity_id, action, actor_name, actor_role, reason FROM audit_logs ORDER BY created_at DESC")
    for ar in cur.fetchall():
        ws_audit.append([
            ar['id'], format_date_str(ar['created_at']), ar['entity_name'], ar['entity_id'],
            ar['action'], ar['actor_name'], ar['actor_role'], ar['reason'] or ''
        ])

    # -------------------------------------------------------------
    # Apply Visual Styling, Header Colors, Widths across all sheets
    # -------------------------------------------------------------
    for ws in wb.worksheets:
        for col_idx, cell in enumerate(ws[1], start=1):
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = THIN_BORDER

        # Auto-adjust column width
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                cell.border = THIN_BORDER
                val_str = str(cell.value or '')
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 40)

        # Highlight Column A:G headers specifically on Deals sheet
        if ws.title.startswith("Deals"):
            for c_i in range(1, 8):
                ws.cell(row=1, column=c_i).fill = ACCENT_FILL
                ws.cell(row=1, column=c_i).font = ACCENT_FONT

    # Record Export in Database log
    import uuid
    export_key = f"EXP-{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{uuid.uuid4().hex[:6]}"
    log_audit(conn, "excel_export", export_key, "EXPORT", "Dhruv Aggarwal", "ADMIN", None, {"sheets_count": 8, "deals_count": len(deal_rows)}, "Generated full multi-sheet workbook")
    conn.execute("""
        INSERT INTO excel_export_logs (id, export_key, version, record_count, sheet_types, exported_by, created_at)
        VALUES (?, ?, 1, ?, 'DEALS,CHAINS,BILLING,BROKERAGE,LEDGER,PRODUCTS,PARTIES,AUDIT', 'Dhruv Aggarwal', ?)
    """, (f"LOG-{export_key}", export_key, len(deal_rows), datetime.now().isoformat()))
    conn.commit()
    conn.close()

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
