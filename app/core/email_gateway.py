"""
Rediffmail & SMTP Email Gateway for Ganesh & Company Brokerage Platform.
Enables automated, 1-click backend sending of official PDF contracts and confirmation notices
directly from the firm's official email (ganeshsgnr@rediffmail.com).
"""

import os
import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.database import get_db_connection, DB_PATH

logger = logging.getLogger("email_gateway")

DEFAULT_REDIFFMAIL_CONFIG = {
    'provider': 'REDIFFMAIL',
    'smtp_host': 'smtp.rediffmail.com',
    'smtp_port': 587,
    'smtp_user': 'ganeshsgnr@rediffmail.com',
    'smtp_pass': '',
    'from_name': 'Ganesh & Company',
    'from_email': 'ganeshsgnr@rediffmail.com',
    'use_ssl': 0, # 0 = STARTTLS (Port 587), 1 = SSL (Port 465)
    'is_enabled': 1
}


def init_email_tables(db_path: str = DB_PATH):
    """Initializes settings table for Rediffmail / SMTP configuration."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            provider TEXT DEFAULT 'REDIFFMAIL',
            smtp_host TEXT DEFAULT 'smtp.rediffmail.com',
            smtp_port INTEGER DEFAULT 587,
            smtp_user TEXT DEFAULT 'ganeshsgnr@rediffmail.com',
            smtp_pass TEXT DEFAULT '',
            from_name TEXT DEFAULT 'Ganesh & Company',
            from_email TEXT DEFAULT 'ganeshsgnr@rediffmail.com',
            use_ssl INTEGER DEFAULT 0,
            is_enabled INTEGER DEFAULT 1,
            updated_at TEXT
        )
    """)
    cur.execute("""
        INSERT OR IGNORE INTO email_config (
            id, provider, smtp_host, smtp_port, smtp_user, smtp_pass, from_name, from_email, use_ssl, is_enabled
        ) VALUES (
            1, 'REDIFFMAIL', 'smtp.rediffmail.com', 587, 'ganeshsgnr@rediffmail.com', '', 'Ganesh & Company', 'ganeshsgnr@rediffmail.com', 0, 1
        )
    """)
    conn.commit()
    conn.close()


def get_email_config(db_path: str = DB_PATH, mask_password: bool = True) -> Dict[str, Any]:
    """Retrieves current Rediffmail / SMTP configuration."""
    init_email_tables(db_path)
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM email_config WHERE id = 1")
    row = cur.fetchone()
    conn.close()

    cfg = dict(row) if row else dict(DEFAULT_REDIFFMAIL_CONFIG)

    # Environment variable overrides if present
    if os.environ.get('REDIFFMAIL_PASS'):
        cfg['smtp_pass'] = os.environ.get('REDIFFMAIL_PASS')
    if os.environ.get('SMTP_HOST'):
        cfg['smtp_host'] = os.environ.get('SMTP_HOST')
    if os.environ.get('SMTP_USER'):
        cfg['smtp_user'] = os.environ.get('SMTP_USER')
        cfg['from_email'] = os.environ.get('SMTP_USER')

    cfg['has_password'] = bool(cfg.get('smtp_pass'))

    if mask_password and cfg.get('smtp_pass'):
        # Mask password for display in UI
        cfg['smtp_pass'] = '••••••••'

    return cfg


def save_email_config(data: Dict[str, Any], db_path: str = DB_PATH) -> Dict[str, Any]:
    """Saves Rediffmail / SMTP configuration."""
    init_email_tables(db_path)
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    current_cfg = get_email_config(db_path, mask_password=False)
    new_pass = data.get('smtp_pass', '')
    if not new_pass or new_pass == '••••••••':
        new_pass = current_cfg.get('smtp_pass', '')

    cur.execute("""
        UPDATE email_config SET
            provider = ?,
            smtp_host = ?,
            smtp_port = ?,
            smtp_user = ?,
            smtp_pass = ?,
            from_name = ?,
            from_email = ?,
            use_ssl = ?,
            is_enabled = ?,
            updated_at = datetime('now')
        WHERE id = 1
    """, (
        data.get('provider', 'REDIFFMAIL'),
        data.get('smtp_host', 'smtp.rediffmail.com').strip(),
        int(data.get('smtp_port', 587)),
        data.get('smtp_user', 'ganeshsgnr@rediffmail.com').strip(),
        new_pass.strip(),
        data.get('from_name', 'Ganesh & Company').strip(),
        data.get('from_email', 'ganeshsgnr@rediffmail.com').strip(),
        1 if data.get('use_ssl') else 0,
        1 if data.get('is_enabled', True) else 0
    ))
    conn.commit()
    conn.close()
    return get_email_config(db_path, mask_password=True)


def _connect_smtp(cfg: Dict[str, Any]) -> smtplib.SMTP:
    """Helper to establish and authenticate SMTP connection."""
    host = cfg.get('smtp_host', 'smtp.rediffmail.com')
    port = int(cfg.get('smtp_port', 587))
    user = cfg.get('smtp_user', 'ganeshsgnr@rediffmail.com')
    password = cfg.get('smtp_pass', '')
    use_ssl = bool(cfg.get('use_ssl', 0)) or port == 465

    if not password:
        raise ValueError("Rediffmail password is not configured. Please enter your password in Rediffmail Settings.")

    if use_ssl:
        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(host, port, context=context, timeout=20)
    else:
        server = smtplib.SMTP(host, port, timeout=20)
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()

    server.login(user, password)
    return server


def test_rediffmail_connection(test_recipient: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Tests Rediffmail SMTP authentication and sends a quick verification email.
    """
    cfg = get_email_config(db_path, mask_password=False)
    if not cfg.get('smtp_pass'):
        return {
            'success': False,
            'error': "Rediffmail password is not set. Please enter your email password and click Save."
        }

    try:
        server = _connect_smtp(cfg)

        from_addr = f"{cfg.get('from_name')} <{cfg.get('from_email')}>"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "✓ Ganesh & Company — Rediffmail SMTP Connection Verified"
        msg["From"] = from_addr
        msg["To"] = test_recipient
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0530")

        text_content = (
            "GANESH & COMPANY — SRI GANGANAGAR (RAJASTHAN)\n"
            "Official Brokerage & Canvassing Automation Platform\n\n"
            "This is a confirmation test email verifying that your Rediffmail SMTP settings "
            f"({cfg.get('smtp_user')} via {cfg.get('smtp_host')}:{cfg.get('smtp_port')}) "
            "are active, authenticated, and ready to deliver official contract PDFs.\n\n"
            f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e5e7eb; border-radius: 8px;">
            <div style="text-align: center; border-bottom: 2px solid #059669; padding-bottom: 16px; margin-bottom: 20px;">
                <h2 style="color: #064e3b; margin: 0; font-size: 20px; text-transform: uppercase;">Ganesh &amp; Company</h2>
                <p style="color: #6b7280; font-size: 13px; margin: 4px 0 0 0;">Sri Ganganagar, Rajasthan &bull; Canvassing Agent (Edible Oil &amp; Oil Cake)</p>
            </div>
            <div style="background-color: #ecfdf5; border-left: 4px solid #10b981; padding: 16px; margin-bottom: 20px;">
                <h3 style="color: #065f46; margin: 0 0 8px 0; font-size: 16px;">✓ Rediffmail SMTP Configuration Active</h3>
                <p style="color: #047857; margin: 0; font-size: 14px;">Your Rediffmail account is successfully connected to the Brokerage Automation Platform.</p>
            </div>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px; color: #374151;">
                <tr><td style="padding: 8px 0; font-weight: bold; width: 40%;">Account:</td><td style="padding: 8px 0;">{cfg.get('smtp_user')}</td></tr>
                <tr><td style="padding: 8px 0; font-weight: bold;">SMTP Server:</td><td style="padding: 8px 0;">{cfg.get('smtp_host')}:{cfg.get('smtp_port')}</td></tr>
                <tr><td style="padding: 8px 0; font-weight: bold;">Verified At:</td><td style="padding: 8px 0;">{datetime.now().strftime('%d %b %Y, %I:%M %p')}</td></tr>
            </table>
            <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #9ca3af; text-align: center;">
                Ganesh &amp; Company Platform &bull; Mob. 94619-40113, 94619-40114 &bull; ganeshsgnr@rediffmail.com
            </div>
        </div>
        """

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        server.sendmail(cfg.get('from_email'), [test_recipient], msg.as_string())
        server.quit()

        return {
            'success': True,
            'message': f"Test email sent successfully from {cfg.get('smtp_user')} to {test_recipient}!"
        }

    except Exception as e:
        logger.error(f"Rediffmail SMTP connection test failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': f"Rediffmail connection failed: {str(e)}"
        }


def send_deal_contract_email(
    deal_dict: Dict[str, Any],
    recipient_email: str,
    recipient_name: Optional[str] = None,
    custom_subject: Optional[str] = None,
    custom_body: Optional[str] = None,
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    """
    Sends an official contract email directly through Rediffmail SMTP with the official
    system-generated PDF attached. Also automatically logs the event in dispatch_logs.
    """
    cfg = get_email_config(db_path, mask_password=False)
    if not cfg.get('smtp_pass'):
        return {
            'success': False,
            'status': 'NEEDS_CONFIG',
            'error': "Rediffmail is not configured. Please enter your Rediffmail password in Settings."
        }

    clean_to = recipient_email.strip()
    if not clean_to or '@' not in clean_to:
        return {
            'success': False,
            'status': 'INVALID_EMAIL',
            'error': f"Invalid recipient email address: '{recipient_email}'"
        }

    bgn = deal_dict.get('bgn_code') or deal_dict.get('id')
    from app.core.pdf_generator import generate_deal_contract_pdf
    pdf_bytes = generate_deal_contract_pdf(deal_dict)
    filename = f"Bargain_Confirmation_{bgn}.pdf"

    subject = custom_subject or f"Bargain Confirmation [{bgn}] — Ganesh & Company, Sri Ganganagar"
    seller_name = deal_dict.get('seller_name', '')
    buyer_name = deal_dict.get('buyer_name', '')
    product_name = deal_dict.get('product_name', '')
    quantity = deal_dict.get('quantity_tonnes', 0)
    rate = deal_dict.get('rate_per_qtl', 0)
    deal_date = deal_dict.get('deal_date', '')
    recip = recipient_name or buyer_name or "Valued Client"

    # Assemble multipart message
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"{cfg.get('from_name')} <{cfg.get('from_email')}>"
    msg["To"] = clean_to
    msg["Reply-To"] = cfg.get('from_email')
    msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0530")

    # Body alternative (plain + html)
    alt_part = MIMEMultipart("alternative")

    text_body = custom_body or (
        f"Dear Sir/Madam ({recip}),\n\n"
        f"Please find attached the official Bargain Confirmation for Bargain No. {bgn}.\n\n"
        f"CONTRACT SUMMARY:\n"
        f"• Bargain No: {bgn}\n"
        f"• Deal Date: {deal_date}\n"
        f"• Seller: {seller_name}\n"
        f"• Buyer: {buyer_name}\n"
        f"• Commodity: {product_name}\n"
        f"• Quantity: {quantity} MT ({int(float(quantity)*10)} Quintals)\n"
        f"• Rate: Rs. {rate:,.2f} Per Quintal + GST\n"
        f"• Payment Date: {deal_dict.get('advance_payment_date') or 'As mutually agreed'}\n"
        f"• Delivery: {deal_dict.get('delivery_condition') or 'Ex-Mill'}\n\n"
        "The official system-generated PDF contract is attached with this email.\n\n"
        "With best regards,\n"
        "For GANESH & COMPANY\n"
        "House No. 2 Friends Colony, Opp. Bansal Petrol Pump, Sri Ganganagar-335001 (Raj.)\n"
        "Mob: 94619-40113, 94619-40114, 94619-40115 | Email: ganeshsgnr@rediffmail.com"
    )

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1f2937; margin: 0; padding: 0; background-color: #f3f4f6; }}
            .container {{ max-width: 640px; margin: 24px auto; background: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
            .header {{ background: #064e3b; color: #ffffff; padding: 24px; text-align: center; border-bottom: 4px solid #10b981; }}
            .header h1 {{ margin: 0; font-size: 22px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; }}
            .header p {{ margin: 6px 0 0 0; font-size: 13px; color: #a7f3d0; }}
            .content {{ padding: 24px; }}
            .card {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 16px; margin: 16px 0; }}
            .table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
            .table td {{ padding: 8px 12px; border-bottom: 1px solid #e5e7eb; }}
            .table td.label {{ color: #6b7280; font-weight: 600; width: 38%; }}
            .table td.val {{ color: #111827; font-weight: 700; }}
            .btn-link {{ display: inline-block; background-color: #059669; color: #ffffff !important; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: 600; font-size: 14px; margin-top: 12px; }}
            .footer {{ background: #f9fafb; padding: 16px 24px; font-size: 12px; color: #6b7280; text-align: center; border-top: 1px solid #e5e7eb; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>GANESH &amp; COMPANY</h1>
                <p>CANVASSING AGENT ALL KIND OF EDIBLE OIL &amp; OIL CAKE &bull; SRI GANGANAGAR</p>
            </div>
            <div class="content">
                <p style="font-size: 15px; margin-top: 0;">Dear <strong>{recip}</strong>,</p>
                <p style="font-size: 14px; color: #4b5563;">
                    We are pleased to confirm the following agricultural commodity bargain executed through our brokerage firm:
                </p>

                <div class="card">
                    <div style="font-size: 12px; font-weight: 700; color: #059669; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;">
                        Contract Summary &bull; {bgn}
                    </div>
                    <table class="table">
                        <tr><td class="label">Bargain No.</td><td class="val">{bgn}</td></tr>
                        <tr><td class="label">Deal Date</td><td class="val">{deal_date}</td></tr>
                        <tr><td class="label">Seller (Mill)</td><td class="val">{seller_name}</td></tr>
                        <tr><td class="label">Buyer</td><td class="val">{buyer_name}</td></tr>
                        <tr><td class="label">Commodity</td><td class="val">{product_name}</td></tr>
                        <tr><td class="label">Quantity</td><td class="val">{quantity} MT ({int(float(quantity)*10)} Qtl)</td></tr>
                        <tr><td class="label">Contract Rate</td><td class="val" style="color: #059669;">Rs. {rate:,.2f} / Qtl + GST</td></tr>
                        <tr><td class="label">Payment Date</td><td class="val">{deal_dict.get('advance_payment_date') or 'As mutually agreed'}</td></tr>
                        <tr><td class="label">Delivery</td><td class="val">{deal_dict.get('delivery_condition') or 'Ex-Mill'}</td></tr>
                    </table>
                </div>

                <div style="background-color: #ecfdf5; border-left: 4px solid #10b981; padding: 14px 16px; border-radius: 4px; margin: 20px 0;">
                    <div style="font-weight: 700; color: #065f46; font-size: 13px;">📎 Official PDF Attached</div>
                    <div style="font-size: 13px; color: #047857; margin-top: 2px;">
                        The full official agreement <strong>{filename}</strong> is attached to this email. Please review the terms and preserve for records.
                    </div>
                </div>

                <p style="font-size: 13px; color: #6b7280; margin-bottom: 0;">
                    Subject to Sri Ganganagar Jurisdiction. For any revisions or queries, please contact our dispatch desk immediately.
                </p>
            </div>
            <div class="footer">
                <strong>GANESH &amp; COMPANY</strong> &bull; Sri Ganganagar-335001 (Rajasthan)<br>
                Proprietor: Sanjay Kumar Aggarwal &bull; Mob. 94619-40113, 94619-40114, 94619-40115<br>
                Official Firm Email: <a href="mailto:ganeshsgnr@rediffmail.com" style="color: #059669;">ganeshsgnr@rediffmail.com</a>
            </div>
        </div>
    </body>
    </html>
    """

    alt_part.attach(MIMEText(text_body, "plain"))
    alt_part.attach(MIMEText(html_body, "html"))
    msg.attach(alt_part)

    # Attach PDF file
    pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    pdf_attachment.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(pdf_attachment)

    try:
        server = _connect_smtp(cfg)
        server.sendmail(cfg.get('from_email'), [clean_to], msg.as_string())
        server.quit()

        # Log dispatch
        recip_type = 'SELLER' if clean_to in str(deal_dict.get('seller_email') or '') else 'BUYER'
        recip_name = deal_dict.get('seller_name') if recip_type == 'SELLER' else deal_dict.get('buyer_name')
        
        try:
            conn = get_db_connection(db_path)
            cur = conn.cursor()
            import uuid
            log_id = f"LOG-{uuid.uuid4().hex[:8].upper()}"
            cur.execute("""
                INSERT INTO dispatch_logs (id, deal_id, recipient_type, recipient_name, channel, phone_or_email, message_preview, status, created_at)
                VALUES (?, ?, ?, ?, 'EMAIL', ?, ?, 'SENT', datetime('now'))
            """, (
                log_id,
                deal_dict.get('id'),
                recip_type,
                recip_name or recip,
                clean_to,
                f"Bargain Confirmation PDF [{bgn}]"
            ))
            conn.commit()
            conn.close()
        except Exception as log_err:
            logger.warning(f"Could not write to dispatch_logs: {log_err}")

        logger.info(f"Successfully sent contract email for deal {bgn} to {clean_to}")
        return {
            'success': True,
            'status': 'SENT',
            'provider': 'REDIFFMAIL',
            'recipient': clean_to,
            'filename': filename,
            'message': f"Official contract PDF delivered to {clean_to} via Rediffmail!"
        }

    except Exception as send_err:
        logger.error(f"Failed to send email via Rediffmail: {send_err}", exc_info=True)
        return {
            'success': False,
            'status': 'SEND_FAILED',
            'error': f"Rediffmail send error: {str(send_err)}"
        }
