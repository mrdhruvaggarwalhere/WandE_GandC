"""
Comprehensive End-to-End API and Workflow Verification Tests.
Validates all REST endpoints, deal chaining, calculations, approval flows, ledger updates, and Excel generation.
"""

import json
import urllib.request
import urllib.error
import pytest
from app.core.database import init_db
from app.core.seed_data import seed_all

BASE_URL = "http://localhost:8080"

def make_request(path: str, method: str = 'GET', data: dict = None, role: str = 'ADMIN'):
    url = f"{BASE_URL}{path}"
    headers = {
        'Content-Type': 'application/json',
        'X-User-Name': 'Test User',
        'X-User-Role': role
    }
    body = json.dumps(data).encode('utf-8') if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content_type = resp.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                return json.loads(resp.read().decode('utf-8'))
            return resp.read()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        raise Exception(f"HTTP {e.code} Error: {err_body}")

def test_dashboard_api():
    data = make_request("/api/dashboard")
    assert "total_active_deals" in data
    assert "total_price_diff_profit" in data
    assert data["total_price_diff_profit"] >= 80000.0
    assert "party_receivables" in data

def test_parties_and_products_api():
    parties = make_request("/api/parties")
    assert len(parties) >= 4
    party_names = [p["legal_name"] for p in parties]
    assert "HARYANA INDUSTRIES, PANCHKULA" in party_names
    assert "SHAKTI NUTRITIONS PVT. LTD." in party_names

    products = make_request("/api/products")
    assert len(products) >= 1
    prod_names = [p["name"] for p in products]
    assert "M.OIL" in prod_names

def test_new_deal_creation_and_reselling_workflow():
    # 1. Create a new root deal
    new_deal_payload = {
        "deal_date": "2026-08-19",
        "seller_id": "PTY-005", # Rajasthan Oil Mills
        "buyer_id": "PTY-007",  # Shree Ganesh Agro
        "product_id": "PRD-001", # M.OIL
        "quantity_qtl": 100.0,
        "rate_per_qtl": 16000.0,
        "delivery_date": "2026-08-30",
        "gst_applicable": 1,
        "buyer_brokerage_rate_per_tonne": 50.0,
        "seller_brokerage_rate_per_tonne": 50.0,
        "notes": "E2E Test Contract 100 Qtl"
    }
    deal_res = make_request("/api/deals", method="POST", data=new_deal_payload)
    chain_id = deal_res["chain_id"]
    deal_id = deal_res["deal_id"]
    assert chain_id.startswith("LOT-")
    assert deal_id.startswith("DL-")

    # 2. Resell the deal
    resell_payload = {
        "chain_id": chain_id,
        "parent_deal_id": deal_id,
        "seller_id": "PTY-007", # Shree Ganesh Agro instructs resale
        "buyer_id": "PTY-006",  # Kuber Edibles buys
        "instruction_date": "2026-08-20",
        "authorized_selling_rate_qtl": 16200.0,
        "actual_sale_rate_qtl": 16300.0, # Diff = +100/qtl -> Profit = 100 * 100 = 10,000
        "quantity_qtl": 100.0,
        "delivery_date": "2026-08-30",
        "buyer_brokerage_rate_per_tonne": 50.0,
        "seller_brokerage_rate_per_tonne": 50.0
    }
    resell_res = make_request("/api/deals/resell", method="POST", data=resell_payload)
    assert resell_res["link_sequence"] == 2
    assert resell_res["price_diff_profit"] == 10000.0

    # 3. Verify Direct Billing Instruction is dynamically resolved
    chain_data = make_request(f"/api/deal-chains/{chain_id}")
    summary = chain_data["summary"]
    assert summary["original_bill_seller"] == "RAJASTHAN OIL MILLS, SRI GANGANAGAR"
    assert summary["final_bill_buyer"] == "KUBER EDIBLES, HISAR"
    assert float(summary["final_rate_per_qtl"]) == 16300.0
    assert float(summary["total_price_diff_profit"]) == 10000.0

def test_billing_instruction_approval_and_busy_preview():
    billings = make_request("/api/billing-instructions")
    assert len(billings) >= 1
    target = billings[0]

    # Approve instruction
    appr_res = make_request(f"/api/billing-instructions/{target['id']}/approve", method="POST", data={"remarks": "Verified by Audit"}, role="ACCOUNTS")
    assert appr_res["approval_status"] == "APPROVED"

    # Preview BUSY XML Voucher
    busy_res = make_request(f"/api/busy/preview/{target['id']}")
    assert "xml_payload" in busy_res
    assert "<VchType>Sales</VchType>" in busy_res["xml_payload"]
    assert target["chain_id"] in busy_res["xml_payload"]

def test_ledger_payment_recording():
    pay_payload = {
        "party_id": "PTY-001",
        "amount": 2500.0,
        "entry_date": "2026-08-19",
        "reference_no": "RTGS-992211",
        "notes": "Settlement of brokerage"
    }
    pay_res = make_request("/api/ledger/payment", method="POST", data=pay_payload, role="ACCOUNTS")
    assert pay_res["entry_id"].startswith("PAY-")
    assert pay_res["amount"] == 2500.0

def test_excel_export_endpoint():
    excel_bytes = make_request("/api/export/excel")
    assert len(excel_bytes) > 2000 # Valid .xlsx binary zip header
    assert excel_bytes[:4] == b'PK\x03\x04' # Zip magic bytes for Office Open XML

def test_worked_example_in_app_runner():
    res = make_request("/api/test/run-worked-example", method="POST")
    assert res["status"] == "PASSED"
    assert res["passed_count"] == res["assertions_count"]
    assert res["total_profit"] == 80000.0
