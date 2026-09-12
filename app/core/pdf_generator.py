"""
Official PDF Contract Generator for Ganesh & Company.
Generates single-page authentic A4 Bargain Confirmation documents matching Sri Ganganagar Mandi specifications.
"""

import io
import os
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
import reportlab.rl_config
reportlab.rl_config.pageCompression = 0

def generate_deal_contract_pdf(deal: Dict[str, Any], recipient_role: Optional[str] = None) -> bytes:
    """
    Generates a byte string containing the official single-page A4 PDF contract.
    Strictly isolates Seller Rate and Buyer Rate based on recipient_role ('SELLER' or 'BUYER').
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=28,
        bottomMargin=24
    )

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    jurisdiction_style = ParagraphStyle(
        'JurisdictionStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#111827'),
        spaceAfter=6
    )

    firm_title_style = ParagraphStyle(
        'FirmTitleStyle',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=20,
        leading=22,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#111827'),
        spaceAfter=3
    )

    sub_box_style = ParagraphStyle(
        'SubBoxStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#111827')
    )

    address_style = ParagraphStyle(
        'AddressStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1F2937'),
        spaceAfter=2
    )

    contact_style = ParagraphStyle(
        'ContactStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#111827')
    )

    doc_title_style = ParagraphStyle(
        'DocTitleStyle',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=13,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#111827'),
        spaceBefore=8,
        spaceAfter=8
    )

    cell_key_style = ParagraphStyle(
        'CellKeyStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#111827')
    )

    cell_val_style = ParagraphStyle(
        'CellValStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#000000')
    )

    clause_title_style = ParagraphStyle(
        'ClauseTitleStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor('#111827'),
        spaceAfter=3
    )

    clause_text_style = ParagraphStyle(
        'ClauseTextStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        leading=8.5,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor('#1F2937'),
        spaceAfter=2
    )

    system_notice_style = ParagraphStyle(
        'SystemNoticeStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=4,
        spaceAfter=2
    )

    system_meta_style = ParagraphStyle(
        'SystemMetaStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=6.5,
        leading=8,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#475569')
    )

    story = []

    # 1. Top Jurisdiction
    story.append(Paragraph("<u>ALL SUBJECT TO SRI GANGANAGAR JURISDICTION</u>", jurisdiction_style))

    # 2. Header Box Table
    header_content = [
        Paragraph("GANESH & COMPANY", firm_title_style),
        Paragraph("<b>CONVASSING AGENT ALL KIND OF EDIBLE OIL &amp; OIL CAKE</b>", sub_box_style),
        Spacer(1, 2),
        Paragraph("House No.2 Friends Colony, Opp.Bahal Petrol Pump, SRIGANGANAGAR-335001", address_style),
        Paragraph("Mob. 94619-40113, 94619-40114, 94619-40115 Sanjay Kumar Aggarwal • Email: ganeshsgnr@rediffmail.com", contact_style)
    ]

    header_table = Table([[header_content]], colWidths=[523])
    header_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#111827')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(header_table)

    # 3. Document Title
    if recipient_role == 'SELLER':
        doc_title_text = "BARGAIN CONFIRMATION (SELLER COPY)"
    elif recipient_role == 'BUYER':
        doc_title_text = "BARGAIN CONFIRMATION (BUYER COPY)"
    else:
        doc_title_text = "BARGAIN CONFIRMATION"
    story.append(Paragraph(f"<u>{doc_title_text}</u>", doc_title_style))

    # 4. Extract deal values safely with rate confidentiality
    bgn = deal.get('bgn_code') or deal.get('id') or 'BGN-001'
    deal_date = str(deal.get('deal_date') or '')
    seller_name = f"{deal.get('seller_name', '')} ({deal.get('seller_station', '')})"
    buyer_name = f"{deal.get('buyer_name', '')} ({deal.get('buyer_station', '')})"
    prod_name = str(deal.get('product_name') or '')
    qty_qtl = float(deal.get('quantity_qtl', 0))
    qty_tonnes = float(deal.get('quantity_tonnes') or (qty_qtl * 0.1))

    # Confidential Rate Isolation
    if recipient_role == 'SELLER':
        rate_val = float(deal.get('seller_rate') if deal.get('seller_rate') is not None else deal.get('rate_per_qtl', 0))
    elif recipient_role == 'BUYER':
        rate_val = float(deal.get('buyer_rate') if deal.get('buyer_rate') is not None else deal.get('rate_per_qtl', 0))
    else:
        rate_val = float(deal.get('seller_rate') or deal.get('rate_per_qtl', 0))

    rate = f"Rs. {round(rate_val):,} + GST Per Qt."
    adv_date = str(deal.get('advance_payment_date') or deal_date)
    delivery = str(deal.get('delivery_condition') or 'Ex-Mill Lifting as per contract')

    grid_data = [
        [Paragraph("Bargain No.", cell_key_style), Paragraph(f"<b>{bgn}</b>", cell_key_style)],
        [Paragraph("Date", cell_key_style), Paragraph(deal_date, cell_val_style)],
        [Paragraph("Seller", cell_key_style), Paragraph(seller_name, cell_val_style)],
        [Paragraph("Buyer", cell_key_style), Paragraph(buyer_name, cell_val_style)],
        [Paragraph("Commodity", cell_key_style), Paragraph(f"<b>{prod_name}</b>", cell_val_style)],
        [Paragraph("Quantity", cell_key_style), Paragraph(f"<b>{qty_tonnes:g} Tons</b> ({qty_qtl:g} Quintals)", cell_val_style)],
        [Paragraph("Rate", cell_key_style), Paragraph(f"<b>{rate}</b>", cell_val_style)],
        [Paragraph("Advance Payment Date", cell_key_style), Paragraph(adv_date, cell_val_style)],
        [Paragraph("Delivery Condition", cell_key_style), Paragraph(delivery, cell_val_style)],
    ]

    grid_table = Table(grid_data, colWidths=[160, 363])
    grid_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.2, colors.HexColor('#111827')),
        ('INNERGRID', (0, 0), (-1, -1), 0.6, colors.HexColor('#111827')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8FAFC')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(grid_table)

    story.append(Spacer(1, 8))

    # 5. Signature Section
    sig_data = [
        ["", Paragraph("<b>For Ganesh &amp; Company</b><br/><br/><br/>Proprietor", ParagraphStyle('Sig', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, alignment=TA_RIGHT))]
    ]
    sig_table = Table(sig_data, colWidths=[360, 163])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(sig_table)

    story.append(Spacer(1, 4))

    # 6. Terms & Conditions
    story.append(Paragraph("<u>TERMS &amp; CONDITIONS:</u>", clause_title_style))
    story.append(Paragraph("<b>1.</b> This contract is confirmed by us as Canvassing Agents between the Buyer and Seller above named, subject to the mutual trade rules and customs of the Sri Ganganagar Mandi.", clause_text_style))
    story.append(Paragraph("<b>2.</b> Advance payment must be remitted strictly by the Buyer on or before the due date stipulated above. In default, Seller reserves the right to cancel or resell the goods at Buyer's risk and cost.", clause_text_style))
    story.append(Paragraph("<b>3.</b> Delivery and lifting shall be effected strictly as per the delivery schedule above. Demurrage, detention, and leakage charges during transit shall be borne as per mutual agreement.", clause_text_style))
    story.append(Paragraph("<b>4.</b> Quality dispute, weight shortage or FFA variation if any, must be reported in writing within 24 hours of tanker arrival at the destination with authorized independent surveyor report.", clause_text_style))
    story.append(Paragraph("<b>5.</b> As Canvassing Agents, Ganesh &amp; Company facilitates deals in good faith and does not guarantee solvency, financial default, or contractual performance of either counterparty.", clause_text_style))
    story.append(Paragraph("<b>6.</b> In the event of any arbitration, dispute, claim or difference arising out of or in connection with this bargain confirmation, the courts at <u>SRI GANGANAGAR (RAJASTHAN)</u> alone shall have exclusive jurisdiction.", clause_text_style))

    # 7. System Generated Notice
    story.append(Spacer(1, 4))
    story.append(Paragraph("*** THIS BARGAIN CONFIRMATION IS A SYSTEM GENERATED DOCUMENT • NO PHYSICAL SIGNATURE IS REQUIRED ***", system_notice_style))
    story.append(Paragraph(f"Computer Generated via Ganesh &amp; Company Platform • Sri Ganganagar (Raj.) Jurisdiction", system_meta_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
