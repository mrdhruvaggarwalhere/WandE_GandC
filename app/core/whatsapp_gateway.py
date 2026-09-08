"""
Automated WhatsApp Gateway for Ganesh & Company.
Enables 100% automated background sending of PDF contracts and confirmation messages
via free gateways (Green API Developer Free Tier, Meta Cloud API Free Tier, or UltraMsg).
"""

import os
import json
import logging
import sqlite3
from typing import Dict, Any, Optional
import requests

from app.core.database import get_db_connection, DB_PATH

logger = logging.getLogger("whatsapp_gateway")

def init_whatsapp_tables(db_path: str = DB_PATH):
    """Initializes settings table for WhatsApp Gateway configuration."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS whatsapp_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            provider TEXT DEFAULT 'GREEN_API',
            instance_id TEXT DEFAULT '',
            api_token TEXT DEFAULT '',
            phone_number_id TEXT DEFAULT '',
            is_enabled INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)
    cur.execute("INSERT OR IGNORE INTO whatsapp_config (id, provider, is_enabled) VALUES (1, 'GREEN_API', 0)")
    conn.commit()
    conn.close()

def get_whatsapp_config(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Retrieves current WhatsApp Gateway configuration."""
    init_whatsapp_tables(db_path)
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM whatsapp_config WHERE id = 1")
    row = cur.fetchone()
    conn.close()

    cfg = dict(row) if row else {'provider': 'GREEN_API', 'is_enabled': 0}
    # Environment variable fallbacks
    if os.environ.get('GREEN_API_INSTANCE_ID') and not cfg.get('instance_id'):
        cfg['instance_id'] = os.environ.get('GREEN_API_INSTANCE_ID')
        cfg['api_token'] = os.environ.get('GREEN_API_TOKEN', '')
        cfg['provider'] = 'GREEN_API'
        cfg['is_enabled'] = 1
    return cfg

def save_whatsapp_config(data: Dict[str, Any], db_path: str = DB_PATH) -> Dict[str, Any]:
    """Saves WhatsApp Gateway credentials."""
    init_whatsapp_tables(db_path)
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    from datetime import datetime
    now_iso = datetime.now().isoformat()

    provider = data.get('provider', 'GREEN_API')
    instance_id = str(data.get('instance_id', '')).strip()
    api_token = str(data.get('api_token', '')).strip()
    phone_number_id = str(data.get('phone_number_id', '')).strip()
    is_enabled = 1 if (instance_id and api_token) or data.get('is_enabled') else 0

    cur.execute("""
        UPDATE whatsapp_config
        SET provider = ?,
            instance_id = ?,
            api_token = ?,
            phone_number_id = ?,
            is_enabled = ?,
            updated_at = ?
        WHERE id = 1
    """, (provider, instance_id, api_token, phone_number_id, is_enabled, now_iso))
    conn.commit()
    conn.close()

    return get_whatsapp_config(db_path)

def send_whatsapp_pdf_document(
    phone_number: str,
    pdf_bytes: bytes,
    filename: str,
    caption: str,
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    """
    Sends a PDF document directly into the WhatsApp chat of the recipient.
    """
    cfg = get_whatsapp_config(db_path)

    # Format phone number to international standard without '+' or special characters
    clean_phone = "".join(filter(str.isdigit, str(phone_number)))
    if len(clean_phone) == 10:
        clean_phone = f"91{clean_phone}" # Default to India country code for 10-digit mandi mobile numbers

    if not cfg.get('is_enabled') or not cfg.get('instance_id') or not cfg.get('api_token'):
        return {
            'success': False,
            'status': 'GATEWAY_NOT_CONFIGURED',
            'message': 'WhatsApp Gateway is not yet connected with API credentials. Please set up your free Green API or Cloud API instance in WhatsApp Settings.',
            'phone': clean_phone,
            'filename': filename
        }

    provider = cfg.get('provider', 'GREEN_API')

    # =========================================================================
    # 1. GREEN API (100% Free Developer Plan)
    # =========================================================================
    if provider == 'GREEN_API':
        instance_id = cfg.get('instance_id')
        api_token = cfg.get('api_token')
        chat_id = f"{clean_phone}@c.us"

        url = f"https://api.green-api.com/waInstance{instance_id}/sendFileByUpload/{api_token}"

        files = {
            'file': (filename, pdf_bytes, 'application/pdf')
        }
        data = {
            'chatId': chat_id,
            'caption': caption,
            'fileName': filename
        }

        try:
            resp = requests.post(url, data=data, files=files, timeout=30)
            result = resp.json()
            if resp.status_code == 200 and 'idMessage' in result:
                return {
                    'success': True,
                    'status': 'SENT',
                    'message_id': result.get('idMessage'),
                    'provider': 'GREEN_API',
                    'chat_id': chat_id,
                    'filename': filename
                }
            else:
                return {
                    'success': False,
                    'status': 'GATEWAY_ERROR',
                    'error': str(result),
                    'http_status': resp.status_code
                }
        except Exception as e:
            logger.exception("Error sending PDF via Green API")
            return {
                'success': False,
                'status': 'NETWORK_ERROR',
                'error': str(e)
            }

    # =========================================================================
    # 2. ULTRAMSG
    # =========================================================================
    elif provider == 'ULTRAMSG':
        instance_id = cfg.get('instance_id')
        api_token = cfg.get('api_token')
        url = f"https://api.ultramsg.com/{instance_id}/messages/document"

        # UltraMsg accepts document URL or base64
        import base64
        pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
        doc_data_uri = f"data:application/pdf;base64,{pdf_b64}"

        payload = {
            'token': api_token,
            'to': clean_phone,
            'filename': filename,
            'document': doc_data_uri,
            'caption': caption
        }

        try:
            resp = requests.post(url, data=payload, timeout=30)
            result = resp.json()
            if result.get('sent') == 'true' or 'id' in result:
                return {
                    'success': True,
                    'status': 'SENT',
                    'message_id': result.get('id'),
                    'provider': 'ULTRAMSG'
                }
            else:
                return {
                    'success': False,
                    'status': 'GATEWAY_ERROR',
                    'error': str(result)
                }
        except Exception as e:
            return {'success': False, 'status': 'NETWORK_ERROR', 'error': str(e)}

    return {
        'success': False,
        'status': 'UNSUPPORTED_PROVIDER',
        'message': f"Provider {provider} not supported."
    }
