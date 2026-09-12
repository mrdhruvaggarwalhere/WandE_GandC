import json
import urllib.request
import urllib.error
import pytest
from app.core.database import get_db_connection, init_db
from app.core.pdf_generator import generate_deal_contract_pdf
from app.core.whatsapp_gateway import format_whatsapp_bargain_message
from app.core.email_gateway import send_deal_contract_emails_both

BASE_URL = "http://127.0.0.1:8080"

def api_get(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {}
        return e.code, body

def api_post(path, data):
    url = f"{BASE_URL}{path}"
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {}
        return e.code, body


def test_pruned_endpoints_return_404():
    """Verify Market Rates and Reports endpoints have been completely pruned."""
    code_mr, _ = api_get("/api/market-rates")
    assert code_mr == 404, f"Expected 404 for removed market-rates, got {code_mr}"

    code_rep, _ = api_get("/api/reports")
    assert code_rep == 404, f"Expected 404 for removed reports, got {code_rep}"


def test_dual_rate_creation_and_persistence():
    """Verify deal creation supports separate seller_rate and buyer_rate."""
    deal_payload = {
        "deal_date": "2026-09-11",
        "seller_id": "PTY-005",
        "buyer_id": "PTY-007",
        "product_id": "PRD-001",
        "quantity_qtl": 150.0,
        "seller_rate": 5350.0,
        "buyer_rate": 5380.0,
        "delivery_terms": "FOR Alwar",
        "payment_terms": "10 Days CAD"
    }
    code, resp = api_post("/api/deals", deal_payload)
    assert code == 201, f"Failed creating deal: {resp}"
    deal_id = resp["deal_id"]

    # Verify directly in database
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT seller_rate, buyer_rate, reconfirmation_required FROM deals WHERE id = ?", (deal_id,))
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row["seller_rate"] == 5350.0
    assert row["buyer_rate"] == 5380.0
    assert row["reconfirmation_required"] == 0


def test_strict_rate_confidentiality_in_pdf():
    """Verify Seller Copy PDF does NOT contain Buyer Rate and Buyer Copy does NOT contain Seller Rate."""
    deal_data = {
        "deal_id": "TEST-CONF-001",
        "deal_date": "2026-09-11",
        "seller_id": "PTY-005",
        "buyer_id": "PTY-007",
        "seller_name": "Haryana Agro Industries",
        "buyer_name": "Shakti Oil Extractions",
        "product_id": "PRD-001",
        "product_name": "Mustard Oil Loose",
        "quantity_mt": 10.0,
        "quantity_qtl": 100.0,
        "seller_rate": 5111.0,
        "buyer_rate": 5222.0,
        "rate_per_qtl": 5111.0,
        "delivery_terms": "Ex-Mill",
        "payment_terms": "Immediate",
        "brokerage_rate_seller": 0.0,
        "brokerage_rate_buyer": 0.0,
        "notes": "Strict confidentiality test"
    }

    # Generate Seller Copy
    seller_pdf_bytes = generate_deal_contract_pdf(deal_data, recipient_role="SELLER")
    seller_pdf_str = seller_pdf_bytes.decode("latin1", errors="ignore")
    assert "5,111" in seller_pdf_str, "Seller rate 5,111 must be present in Seller Copy"
    assert "5,222" not in seller_pdf_str, "Buyer rate 5,222 must NEVER leak into Seller Copy"
    assert "SELLER COPY" in seller_pdf_str

    # Generate Buyer Copy
    buyer_pdf_bytes = generate_deal_contract_pdf(deal_data, recipient_role="BUYER")
    buyer_pdf_str = buyer_pdf_bytes.decode("latin1", errors="ignore")
    assert "5,222" in buyer_pdf_str, "Buyer rate 5,222 must be present in Buyer Copy"
    assert "5,111" not in buyer_pdf_str, "Seller rate 5,111 must NEVER leak into Buyer Copy"
    assert "BUYER COPY" in buyer_pdf_str


def test_strict_rate_confidentiality_in_whatsapp():
    """Verify WhatsApp messages send only the recipient's respective rate."""
    deal_data = {
        "deal_id": "TEST-CONF-WA-002",
        "deal_date": "2026-09-11",
        "seller_name": "Haryana Agro",
        "buyer_name": "Shakti Oil",
        "product_name": "Mustard Oil",
        "quantity_mt": 15.0,
        "quantity_qtl": 150.0,
        "seller_rate": 5400.0,
        "buyer_rate": 5450.0,
        "delivery_terms": "Ex-Factory",
        "payment_terms": "Immediate"
    }

    seller_text = format_whatsapp_bargain_message(deal_data, role="SELLER")
    assert "5,400" in seller_text
    assert "5,450" not in seller_text
    assert "SELLER COPY" in seller_text

    buyer_text = format_whatsapp_bargain_message(deal_data, role="BUYER")
    assert "5,450" in buyer_text
    assert "5,400" not in buyer_text
    assert "BUYER COPY" in buyer_text


def test_dual_dispatch_email_isolation_and_reporting():
    """Verify send_deal_contract_emails_both delivers isolated PDFs and reports dual status."""
    deal_data = {
        "deal_id": "TEST-EMAIL-003",
        "deal_date": "2026-09-11",
        "seller_id": "PTY-005",
        "buyer_id": "PTY-007",
        "seller_name": "Haryana Agro Industries",
        "buyer_name": "Shakti Oil Extractions",
        "product_id": "PRD-001",
        "product_name": "Mustard Oil Loose",
        "quantity_mt": 10.0,
        "quantity_qtl": 100.0,
        "seller_rate": 5300.0,
        "buyer_rate": 5350.0,
        "rate_per_qtl": 5300.0,
        "delivery_terms": "FOR",
        "payment_terms": "CAD"
    }
    # Both fail gracefully in mock/offline mode without crashing, reporting status accurately
    result = send_deal_contract_emails_both(deal_data)
    assert "seller" in result
    assert "buyer" in result
    assert result["seller"]["role"] == "SELLER"
    assert result["buyer"]["role"] == "BUYER"
    assert "partial" in result


def test_inplace_bargain_edit_and_reconfirmation_flag():
    """Verify in-place editing preserves Deal ID and flags commercial changes."""
    # 1. Create initial deal
    deal_payload = {
        "deal_date": "2026-09-11",
        "seller_id": "PTY-005",
        "buyer_id": "PTY-007",
        "product_id": "PRD-001",
        "quantity_qtl": 200.0,
        "seller_rate": 5000.0,
        "buyer_rate": 5000.0,
        "delivery_terms": "Ex-Mill",
        "payment_terms": "CAD 7 Days"
    }
    code, resp = api_post("/api/deals", deal_payload)
    assert code == 201, f"Failed creating deal: {resp}"
    deal_id = resp["deal_id"]

    # 2. Non-commercial edit (notes only) -> reconfirmation_required should stay 0
    edit_payload_1 = {
        "deal_date": "2026-09-11",
        "seller_id": "PTY-005",
        "buyer_id": "PTY-007",
        "product_id": "PRD-001",
        "quantity_qtl": 200.0,
        "seller_rate": 5000.0,
        "buyer_rate": 5000.0,
        "delivery_terms": "Ex-Mill",
        "payment_terms": "CAD 7 Days",
        "notes": "Driver contact updated"
    }
    code_edit1, resp_edit1 = api_post(f"/api/deals/{deal_id}/edit", edit_payload_1)
    assert code_edit1 == 200
    assert resp_edit1["id"] == deal_id
    assert resp_edit1["reconfirmation_required"] == 0

    # 3. Commercial edit (rate change: seller_rate changed to 5050) -> reconfirmation_required becomes 1
    edit_payload_2 = dict(edit_payload_1)
    edit_payload_2["seller_rate"] = 5050.0
    code_edit2, resp_edit2 = api_post(f"/api/deals/{deal_id}/edit", edit_payload_2)
    assert code_edit2 == 200
    assert resp_edit2["id"] == deal_id
    assert resp_edit2["reconfirmation_required"] == 1
    assert resp_edit2["seller_rate"] == 5050.0


def test_bulk_soft_delete_and_restore():
    """Verify multi-select bulk soft delete and bulk restore lifecycle."""
    # Create two deals
    d1_payload = {
        "deal_date": "2026-09-11",
        "seller_id": "PTY-005",
        "buyer_id": "PTY-007",
        "product_id": "PRD-001",
        "quantity_qtl": 100.0,
        "seller_rate": 5100.0,
        "buyer_rate": 5100.0
    }
    _, r1 = api_post("/api/deals", d1_payload)
    id1 = r1["deal_id"]

    d2_payload = {
        "deal_date": "2026-09-11",
        "seller_id": "PTY-005",
        "buyer_id": "PTY-007",
        "product_id": "PRD-001",
        "quantity_qtl": 120.0,
        "seller_rate": 5120.0,
        "buyer_rate": 5120.0
    }
    _, r2 = api_post("/api/deals", d2_payload)
    id2 = r2["deal_id"]

    # Bulk delete both
    code_del, resp_del = api_post("/api/deals/bulk-delete", {"deal_ids": [id1, id2]})
    assert code_del == 200
    assert resp_del["count"] == 2

    # Verify both are marked deleted in database
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, deleted_at FROM deals WHERE id IN (?, ?)", (id1, id2))
    rows = cur.fetchall()
    conn.close()
    assert len(rows) == 2
    for r in rows:
        assert r["deleted_at"] is not None

    # Bulk restore both
    code_res, resp_res = api_post("/api/deals/bulk-restore", {"deal_ids": [id1, id2]})
    assert code_res == 200
    assert resp_res["count"] == 2

    # Verify both are restored
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, deleted_at FROM deals WHERE id IN (?, ?)", (id1, id2))
    restored_rows = cur.fetchall()
    conn.close()
    assert len(restored_rows) == 2
    for r in restored_rows:
        assert r["deleted_at"] is None
