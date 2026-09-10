import json
import pytest
from app.server import BrokerageHTTPRequestHandler
from app.core.database import get_db_connection, DB_PATH

def test_deal_dispatch_status_subqueries():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            d.id, COALESCE(d.bgn_code, d.id) AS bgn_code,
            (SELECT status FROM dispatch_logs WHERE (deal_id = d.id OR deal_id = d.bgn_code) AND channel = 'WHATSAPP' ORDER BY created_at DESC LIMIT 1) AS wa_status,
            (SELECT status FROM dispatch_logs WHERE (deal_id = d.id OR deal_id = d.bgn_code) AND channel = 'EMAIL' ORDER BY created_at DESC LIMIT 1) AS email_status
        FROM deals d
        LIMIT 5
    """)
    rows = cur.fetchall()
    conn.close()
    assert len(rows) > 0
    # Every row contains wa_status and email_status fields
    for r in rows:
        assert 'wa_status' in r.keys()
        assert 'email_status' in r.keys()

def test_dispatch_logs_query_format():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT channel, status, phone_or_email, created_at 
        FROM dispatch_logs
        ORDER BY created_at DESC
        LIMIT 5
    """)
    logs = [dict(r) for r in cur.fetchall()]
    conn.close()
    for log in logs:
        assert log['channel'] in ('WHATSAPP', 'EMAIL')
        assert log['status'] in ('SENT', 'FAILED', 'PENDING', 'DELIVERED')
