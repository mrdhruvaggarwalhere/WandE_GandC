# G&C Central Deal and Brokerage Automation Platform

A complete, production-grade automation layer designed for edible-oil brokers. It eliminates redundant data entry, automatically manages multi-leg resale chains, calculates price-difference profit and per-tonne brokerage, dynamically resolves the original seller and final buyer for direct commercial billing, provides multi-sheet Excel exports conforming to standard broker conventions, and prepares staging vouchers for BUSY accounting software.

---

## Key Capabilities

1. **Single-Entry Deal Capture**: Record purchase commitments once with party defaults, auto-converting quintals to metric tonnes, live GST breakdowns, and custom brokerage overrides.
2. **Deal Chaining & Resale Management**: Link subsequent resale instructions, track remaining unresold balances, record party authorized selling rates vs. actual broker execution rates, and compute price-difference margins.
3. **Exact Decimal Financial Arithmetic**: Zero floating-point drift using server-side decimal math for currency, quintal-to-tonne conversions, positive/negative price differences, and buyer/seller brokerage splits.
4. **Dynamic Direct-Billing Resolution**: Automatically identifies the root seller (*Original Bill Seller*) and terminal buyer (*Final Bill Buyer*) to formulate the official direct-billing instruction:
   > **[Original Bill Seller] will issue a direct bill to [Final Bill Buyer] for [Quantity] quintals of [Product] at ₹[Final Rate] + GST per quintal.**
5. **Excel Automation Engine**: Multi-sheet `.xlsx` export preserving strict **Columns A:G mapping** (`Deal Date`, `Buyer`, `Seller`, `Product`, `Quantity`, `Price & GST`, `Delivery Date`) followed by extended analytical columns (Chain ID, Profit, Brokerage breakdown, Direct Bill resolution).
6. **BUSY Accounting Integration Adapter**: Staging hub producing XML and JSON vouchers for BUSY 18/21 import utilities with strict safeguards preventing intermediate chain records from accidental commercial invoice posting.
7. **Multi-Role Access & Permissions**: Built-in support and instant UI switcher for **Administrator**, **Broker/Operator**, **Accounts**, and **Viewer** roles.
8. **Automated Verification & Test Runner**: Built-in test runner validating the mandatory **Haryana Industries → Nagpal Enterprises → M.L. Nagpal → Shakti Nutritions** scenario.

---

## Directory Structure

```text
gc-brokerage-platform/
├── app/
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css            # Modern Glassmorphic Vanilla CSS design system
│   │   └── js/
│   │       ├── app.js               # SPA router, state manager, toast notifications
│   │       ├── deal_entry.js        # Keyboard-friendly fast deal entry & live calculators
│   │       ├── deal_chain.js        # Interactive deal chain visualizer & resale linking
│   │       ├── billing.js           # Direct billing instructions & review/approval workflow
│   │       ├── ledger.js            # Party ledger, brokerage statements & payment capture
│   │       ├── reports.js           # Reports suite (Deal register, profit report, dues)
│   │       ├── masters.js           # Party & Product master managers
│   │       ├── busy_adapter.js      # BUSY accounting XML / JSON voucher viewer
│   │       └── test_runner.js       # Live in-browser acceptance test runner
│   ├── templates/
│   │   └── index.html               # Responsive HTML5 single-page application
│   ├── core/
│   │   ├── __init__.py
│   │   ├── calculations.py          # Exact Decimal financial calculation engine
│   │   ├── database.py              # Normalized SQLite schema, migrations & audit log
│   │   ├── seed_data.py             # Seed data with mandatory worked example
│   │   ├── excel_exporter.py        # Multi-sheet styled Excel workbook generator
│   │   └── busy_adapter.py          # BUSY XML & JSON voucher generator
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py                # REST API controllers
│   └── server.py                    # High-performance HTTP server
├── tests/
│   ├── __init__.py
│   ├── test_calculations.py         # Unit tests for financial formulas & conversions
│   ├── test_excel_export.py         # Excel multi-sheet & Column A:G mapping test
│   ├── test_haryana_worked_example.py # Mandatory worked example integration test
│   └── test_e2e_api.py              # End-to-end REST API & workflow test suite
├── requirements.txt
├── README.md
└── run.py                           # Quick launch script
```

---

## Calculation Rules Reference

| Metric | Mathematical Formula | Notes |
|---|---|---|
| **Unit Conversion** | $\text{MT} = \text{Quintals} / 10$ | 1 Metric Tonne = 10 Quintals (1,000 kg) |
| **Price Difference** | $\text{Rate}_{\text{actual}} - \text{Rate}_{\text{authorized}}$ | Per quintal rate difference |
| **Price-Diff Profit** | $\text{Price Difference} \times \text{Quantity (Quintals)}$ | Positive (profit) or negative (loss) |
| **Buyer Brokerage** | $\text{Quantity (MT)} \times \text{Buyer Rate (₹/MT)}$ | Defaults from Party Master |
| **Seller Brokerage** | $\text{Quantity (MT)} \times \text{Seller Rate (₹/MT)}$ | Defaults from Party Master |
| **Deal Brokerage** | $\text{Buyer Brokerage} + \text{Seller Brokerage}$ | Stored per deal |
| **Total Chain Earning** | $\sum \text{Price-Diff Profit} + \sum \text{Brokerage}$ | Separate breakdown preserved |

---

## Mandatory Acceptance Test Verification

The platform was tested against the scenario specified in the prompt:

1. **Initial Purchase (01/07/2026):**
   - Buyer: HARYANA INDUSTRIES, PANCHKULA
   - Seller: NAGPAL ENTERPRISES PVT. LTD., ANOUPGARH
   - Product: M.OIL | Quantity: 320 quintals (32 metric tonnes)
   - Rate: ₹15,700 + GST / quintal
2. **First Resale Link (18/07/2026):**
   - Haryana Industries authorizes selling rate @ ₹16,450 / quintal
   - Broker sells to M.L. NAGPAL INDUSTRIES, ANOUPGARH @ ₹16,475 + GST / quintal
   - Price difference: **₹25 / quintal**
   - Price-difference profit: **₹25 × 320 = ₹8,000**
3. **Second Resale Link (30/07/2026 → 11/08/2026):**
   - M.L. NAGPAL INDUSTRIES authorizes selling rate @ ₹16,475 / quintal
   - Broker sells to SHAKTI NUTRITIONS PVT. LTD. @ ₹16,700 + GST / quintal
   - Price difference: **₹225 / quintal**
   - Price-difference profit: **₹225 × 320 = ₹72,000**
4. **Chain Results:**
   - Total price-difference profit: **₹80,000** (₹8,000 + ₹72,000)
   - Direct Billing: **NAGPAL ENTERPRISES PVT. LTD., ANOUPGARH will issue a direct bill to SHAKTI NUTRITIONS PVT. LTD. for 320 quintals of M.OIL at ₹16,700.00 + GST per quintal.**

---

## Running Locally

### 1. Launch the Web Application
```bash
cd /Users/mrdhruvaggarwal/.gemini/antigravity-ide/scratch/gc-brokerage-platform
.venv/bin/python3 run.py
```
Open **http://localhost:8080** in your browser.

### 2. Execute Automated Test Suite
```bash
cd /Users/mrdhruvaggarwal/.gemini/antigravity-ide/scratch/gc-brokerage-platform
PYTHONPATH=. .venv/bin/pytest -v
```
