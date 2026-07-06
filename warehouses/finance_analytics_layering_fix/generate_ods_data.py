#!/usr/bin/env python3
"""
生成 warehouses/finance_analytics/ods/data/internal/finance_analytics_dm 下的 ODS 初始化 SQL。
"""

from __future__ import annotations

import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

_src_root = Path(__file__).resolve().parents[2] / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from dw_refactor_agent.config import TEXT_ENCODING

PROJECT_DIR = Path(__file__).resolve().parent
DBT_ROOT = Path(__file__).resolve().parents[2] / "finance_analytics_dbt"
DB_NAME = "finance_analytics_dm"
ODS_DATA_DIR = PROJECT_DIR / "ods" / "data" / "internal" / DB_NAME
LOAD_TIME = datetime(2025, 1, 15, 9, 0, 0)

random.seed(42)


GEO = [
    ("New York", "NY", "Northeast", 40.7128, -74.0060),
    ("Boston", "MA", "Northeast", 42.3601, -71.0589),
    ("Chicago", "IL", "Midwest", 41.8781, -87.6298),
    ("Dallas", "TX", "Southwest", 32.7767, -96.7970),
    ("San Francisco", "CA", "West", 37.7749, -122.4194),
    ("Seattle", "WA", "West", 47.6062, -122.3321),
    ("Miami", "FL", "Southeast", 25.7617, -80.1918),
    ("Atlanta", "GA", "Southeast", 33.7490, -84.3880),
]


def load_source_columns() -> dict[str, list[str]]:
    data = yaml.safe_load(
        (DBT_ROOT / "models" / "ingestion" / "sources.yml").read_text(
            encoding=TEXT_ENCODING
        )
    )
    tables: dict[str, list[str]] = {}
    for source in data.get("sources", []):
        for table in source.get("tables", []):
            tables[table["name"]] = [
                col["name"] for col in table.get("columns", [])
            ] + ["load_time"]
    return tables


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        return f"'{value.isoformat(sep=' ')}'"
    if isinstance(value, date):
        return f"'{value.isoformat()}'"
    if isinstance(value, str):
        return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"
    return str(value)


def render_insert(
    table: str, columns: list[str], rows: list[dict[str, Any]]
) -> str:
    values_sql = []
    for row in rows:
        ordered = [sql_literal(row.get(col)) for col in columns]
        values_sql.append("(" + ", ".join(ordered) + ")")
    cols_sql = ", ".join(
        f"`{col}`" if col[0].isdigit() else col for col in columns
    )
    return (
        f"INSERT INTO {DB_NAME}.ods_{table} ({cols_sql})\nVALUES\n"
        + ",\n".join(values_sql)
        + ";\n"
    )


def dt(days: int, hour: int = 9) -> datetime:
    return datetime(2025, 1, 1, hour, 0, 0) + timedelta(days=days)


def build_products() -> list[dict[str, Any]]:
    products = [
        (1, "Checking Account", "Deposit", 0.01, 0, 0, 100, "Basic", False),
        (2, "Savings Account", "Deposit", 0.03, 100, 0, 0, "Standard", False),
        (3, "Rewards Credit Card", "Credit", 0.18, 0, 0, 0, "Premium", True),
        (4, "Personal Loan", "Loan", 0.08, 0, 0, 0, "Standard", False),
        (5, "Mortgage", "Loan", 0.05, 0, 0, 0, "Premium", True),
        (
            6,
            "Investment Account",
            "Investment",
            0.00,
            1000,
            25,
            0,
            "Premium",
            True,
        ),
    ]
    rows = []
    for idx, item in enumerate(products):
        rows.append(
            {
                "product_id": item[0],
                "product_name": item[1],
                "category": item[2],
                "interest_rate": item[3],
                "min_balance": item[4],
                "monthly_fee": item[5],
                "overdraft_limit": item[6],
                "product_tier": item[7],
                "is_premium": item[8],
                "created_at": dt(idx),
                "load_time": LOAD_TIME,
            }
        )
    return rows


def build_merchants() -> list[dict[str, Any]]:
    categories = [
        ("Fresh Mart", "Grocery", 5411, False),
        ("Fuel Point", "Gas Station", 5541, False),
        ("Cloud Store", "Online Shopping", 5969, True),
        ("Health Hub", "Healthcare", 8099, False),
        ("Travel Air", "Travel", 4511, True),
        ("Cinema City", "Entertainment", 7832, False),
        ("Cafe Nova", "Restaurant", 5812, False),
        ("Home Fix", "Services", 7349, False),
    ]
    rows = []
    for idx, item in enumerate(categories, start=1):
        city, state, _, lat, lng = GEO[idx % len(GEO)]
        rows.append(
            {
                "merchant_id": idx,
                "merchant_name": item[0],
                "category": item[1],
                "mcc_code": item[2],
                "city": city,
                "state": state,
                "country": "USA",
                "latitude": lat,
                "longitude": lng,
                "risk_rating": random.choice(["Low", "Medium", "High"]),
                "avg_transaction_amount": round(random.uniform(25, 600), 2),
                "is_online": item[3],
                "established_date": date(
                    2005 + idx, (idx % 12) + 1, min(20, idx + 5)
                ),
                "created_at": dt(idx),
                "load_time": LOAD_TIME,
            }
        )
    return rows


def build_customers() -> list[dict[str, Any]]:
    first_names = [
        "Ava",
        "Liam",
        "Noah",
        "Emma",
        "Olivia",
        "Mia",
        "Ethan",
        "Sophia",
        "Lucas",
        "Amelia",
        "James",
        "Harper",
    ]
    last_names = [
        "Smith",
        "Johnson",
        "Brown",
        "Taylor",
        "Miller",
        "Wilson",
        "Moore",
        "Jackson",
        "White",
        "Harris",
        "Martin",
        "Clark",
    ]
    segments = ["Mass Market", "Affluent", "Premium", "Business"]
    rows = []
    for idx in range(1, 13):
        city, state, _, _, _ = GEO[idx % len(GEO)]
        birth_year = 1965 + idx
        signup = date(2023 + (idx % 2), (idx % 12) + 1, min(idx + 5, 28))
        age = 2025 - birth_year
        rows.append(
            {
                "customer_id": idx,
                "first_name": first_names[idx - 1],
                "last_name": last_names[idx - 1],
                "email": f"customer{idx}@example.com",
                "phone": f"555000{idx:04d}",
                "date_of_birth": date(
                    birth_year, (idx % 12) + 1, min(15, idx + 1)
                ),
                "age": age,
                "ssn": f"900-10-{idx:04d}",
                "address": f"{100 + idx} Main Street",
                "city": city,
                "state": state,
                "zip_code": f"{10000 + idx}",
                "country": "USA",
                "signup_date": signup,
                "credit_score": 580 + idx * 18,
                "annual_income": 45000 + idx * 8500,
                "employment_status": random.choice(
                    ["Employed", "Self-Employed", "Retired", "Student"]
                ),
                "employer": f"Employer {idx}",
                "job_title": random.choice(
                    ["Analyst", "Manager", "Engineer", "Consultant"]
                ),
                "education_level": random.choice(
                    ["High School", "Bachelor", "Master"]
                ),
                "marital_status": random.choice(["Single", "Married"]),
                "number_of_dependents": idx % 3,
                "home_ownership": random.choice(["Own", "Rent", "Mortgage"]),
                "customer_segment": segments[idx % len(segments)],
                "life_stage": random.choice(
                    ["Young Professional", "Family", "Retiree"]
                ),
                "risk_segment": random.choice(["Low", "Medium", "High"]),
                "is_active": idx % 5 != 0,
                "preferred_channel": random.choice(
                    ["Online", "Mobile", "Branch", "Phone"]
                ),
                "marketing_opt_in": idx % 2 == 0,
                "loyalty_tier": random.choice(
                    ["Bronze", "Silver", "Gold", "Platinum"]
                ),
                "customer_lifetime_value": round(5000 + idx * 2200.5, 2),
                "churn_risk_score": round(
                    min(0.95, 0.08 * (idx % 6) + 0.12), 2
                ),
                "last_login_date": date(2025, 1, min(20, idx + 5)),
                "acquisition_channel": random.choice(
                    ["Online", "Branch", "Referral", "Partner"]
                ),
                "created_at": dt(idx),
                "load_time": LOAD_TIME,
            }
        )
    return rows


def build_accounts(
    customers: list[dict[str, Any]], products: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    account_id = 1
    for customer in customers:
        choices = [products[(customer["customer_id"] - 1) % len(products)]]
        if customer["customer_id"] % 2 == 0:
            choices.append(
                products[(customer["customer_id"] + 1) % len(products)]
            )
        for prod in choices:
            is_credit = prod["category"] == "Credit"
            is_loan = prod["category"] == "Loan"
            balance = round(random.uniform(500, 80000), 2)
            if is_credit or is_loan:
                balance = -round(random.uniform(500, 20000), 2)
            rows.append(
                {
                    "account_id": account_id,
                    "customer_id": customer["customer_id"],
                    "product_id": prod["product_id"],
                    "account_number": f"000000{account_id:06d}",
                    "account_status": "Active"
                    if customer["is_active"]
                    else random.choice(["Dormant", "Closed"]),
                    "open_date": customer["signup_date"] + timedelta(days=15),
                    "close_date": None
                    if customer["is_active"]
                    else date(2024, 12, min(20, customer["customer_id"] + 5)),
                    "current_balance": balance,
                    "available_balance": max(balance, 0),
                    "credit_limit": 12000 if is_credit else None,
                    "currency": "USD",
                    "interest_rate": prod["interest_rate"],
                    "minimum_payment": round(abs(balance) * 0.03, 2)
                    if is_credit or is_loan
                    else None,
                    "payment_due_date": date(
                        2025, 1, min(28, customer["customer_id"] + 10)
                    )
                    if is_credit or is_loan
                    else None,
                    "last_statement_date": date(
                        2024, 12, min(28, customer["customer_id"] + 8)
                    ),
                    "autopay_enabled": customer["customer_id"] % 2 == 0,
                    "overdraft_protection": prod["category"] == "Deposit",
                    "primary_account": prod["product_id"] in {1, 2},
                    "created_at": dt(customer["customer_id"]),
                    "load_time": LOAD_TIME,
                }
            )
            account_id += 1
    return rows


def build_transactions(
    accounts: list[dict[str, Any]], merchants: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    tx_id = 1
    active_accounts = [
        row for row in accounts if row["account_status"] == "Active"
    ]
    for idx, account in enumerate(active_accounts):
        for step in range(4):
            merchant = merchants[(idx + step) % len(merchants)]
            tx_time = dt(step, 10 + (idx % 8))
            amount = round(random.uniform(20, 1200), 2)
            if step % 3 != 0:
                amount *= -1
            is_fraud = tx_id in {7, 18, 31}
            rows.append(
                {
                    "transaction_id": tx_id,
                    "account_id": account["account_id"],
                    "customer_id": account["customer_id"],
                    "merchant_id": merchant["merchant_id"],
                    "transaction_date": tx_time,
                    "transaction_type": random.choice(
                        ["Purchase", "Payment", "Deposit", "Transfer", "Fee"]
                    ),
                    "amount": amount,
                    "currency": "USD",
                    "channel": random.choice(
                        ["Online", "Mobile", "ATM", "Branch", "POS"]
                    ),
                    "merchant_category": merchant["category"],
                    "mcc_code": merchant["mcc_code"],
                    "description": f"Txn {tx_id} at {merchant['merchant_name']}",
                    "is_fraud": is_fraud,
                    "fraud_score": 0.91
                    if is_fraud
                    else round(random.uniform(0.05, 0.35), 2),
                    "location_city": merchant["city"],
                    "location_state": merchant["state"],
                    "location_country": "USA",
                    "latitude": merchant["latitude"],
                    "longitude": merchant["longitude"],
                    "device_id": f"device-{tx_id:04d}",
                    "ip_address": f"10.0.{tx_id % 20}.{tx_id % 255}",
                    "is_international": merchant["merchant_id"] % 5 == 0,
                    "authorization_code": f"AUTH{tx_id:06d}",
                    "card_last_four": 1000 + (tx_id % 9000),
                    "is_recurring": tx_id % 6 == 0,
                    "hour_of_day": tx_time.hour,
                    "day_of_week": (tx_time.weekday() + 1) % 7,
                    "is_weekend": tx_time.weekday() >= 5,
                    "distance_from_home_km": round(random.uniform(1, 120), 2),
                    "merchant_risk_score": round(random.uniform(0.1, 0.9), 2),
                    "velocity_24h": random.randint(1, 7),
                    "amount_deviation_score": round(
                        random.uniform(0.1, 0.95), 2
                    ),
                    "processing_time_ms": random.randint(120, 2400),
                    "decline_reason": "Fraud Suspected"
                    if is_fraud
                    else (None if tx_id % 9 else "Insufficient Funds"),
                    "created_at": tx_time,
                    "load_time": LOAD_TIME,
                }
            )
            tx_id += 1
    return rows


def build_credit_applications(
    customers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for idx, customer in enumerate(customers, start=1):
        decision = (
            "Approved"
            if customer["credit_score"] >= 680
            else random.choice(["Declined", "Pending"])
        )
        rows.append(
            {
                "application_id": idx,
                "customer_id": customer["customer_id"],
                "product_id": 4 if idx % 2 else 5,
                "application_date": dt(idx % 7),
                "requested_amount": 5000 + idx * 1250,
                "requested_term_months": random.choice([12, 24, 36, 60]),
                "credit_score_at_application": customer["credit_score"],
                "annual_income": customer["annual_income"],
                "debt_to_income_ratio": round(random.uniform(0.12, 0.48), 2),
                "employment_length_years": random.randint(1, 18),
                "decision": decision,
                "decision_date": dt((idx % 7) + 1),
                "approved_amount": 4000 + idx * 900
                if decision == "Approved"
                else None,
                "approved_rate": 0.07 if decision == "Approved" else None,
                "application_channel": random.choice(
                    ["Online", "Branch", "Phone", "Mobile"]
                ),
                "approval_probability_score": round(
                    random.uniform(0.2, 0.95), 2
                ),
                "risk_grade": random.choice(["A", "B", "C", "D"]),
                "created_at": dt(idx % 7),
                "load_time": LOAD_TIME,
            }
        )
    return rows


def build_fraud_alerts(
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    alerts = [tx for tx in transactions if tx["is_fraud"]][:3]
    for idx, tx in enumerate(alerts, start=1):
        rows.append(
            {
                "alert_id": idx,
                "transaction_id": tx["transaction_id"],
                "customer_id": tx["customer_id"],
                "account_id": tx["account_id"],
                "alert_date": tx["transaction_date"] + timedelta(minutes=10),
                "alert_type": random.choice(
                    [
                        "Unusual Spending",
                        "Velocity Check",
                        "High Risk Merchant",
                    ]
                ),
                "alert_severity": random.choice(["High", "Critical"]),
                "investigation_status": random.choice(
                    ["Open", "Under Review", "Resolved - Fraud"]
                ),
                "resolution_date": tx["transaction_date"] + timedelta(days=2),
                "amount_recovered": round(abs(tx["amount"]) * 0.6, 2),
                "assigned_to": f"INV{idx:03d}",
                "notes": f"Investigate transaction {tx['transaction_id']}",
                "created_at": tx["transaction_date"],
                "load_time": LOAD_TIME,
            }
        )
    return rows


def build_customer_interactions(
    customers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for idx, customer in enumerate(customers, start=1):
        rows.append(
            {
                "interaction_id": idx,
                "customer_id": customer["customer_id"],
                "interaction_date": dt(idx % 10, 14),
                "interaction_type": random.choice(
                    ["Phone Call", "Email", "Chat", "Branch Visit"]
                ),
                "reason": random.choice(
                    [
                        "Account Inquiry",
                        "Transaction Dispute",
                        "Complaint",
                        "Technical Support",
                    ]
                ),
                "duration_minutes": random.randint(5, 45),
                "sentiment_score": round(random.uniform(-0.6, 0.8), 2),
                "satisfaction_rating": random.randint(2, 5),
                "resolved": idx % 4 != 0,
                "escalated": idx % 6 == 0,
                "agent_id": f"AG{(idx % 5) + 1:03d}",
                "notes": f"Interaction for customer {customer['customer_id']}",
                "created_at": dt(idx % 10, 14),
                "load_time": LOAD_TIME,
            }
        )
    return rows


def build_economic_indicators() -> list[dict[str, Any]]:
    rows = []
    for idx in range(10):
        rows.append(
            {
                "date": date(2025, 1, idx + 1),
                "gdp_growth_rate": round(2.1 + idx * 0.03, 2),
                "unemployment_rate": round(4.2 - idx * 0.01, 2),
                "inflation_rate": round(2.4 + idx * 0.02, 2),
                "federal_funds_rate": 5.25,
                "sp500_index": 4700 + idx * 12,
                "vix_index": round(14 + idx * 0.4, 2),
                "consumer_confidence_index": round(102 + idx * 0.5, 2),
                "housing_price_index": round(298 + idx * 0.7, 2),
                "10yr_treasury_yield": round(4.0 + idx * 0.01, 2),
                "mortgage_rate_30yr": round(6.4 + idx * 0.01, 2),
                "created_at": dt(idx),
                "load_time": LOAD_TIME,
            }
        )
    return rows


def build_marketing_campaigns() -> list[dict[str, Any]]:
    rows = []
    for idx in range(1, 7):
        start = date(2024, idx, 1)
        rows.append(
            {
                "campaign_id": idx,
                "campaign_name": f"Campaign {idx}",
                "campaign_type": random.choice(
                    ["Email", "Social Media", "Direct Mail", "Online Display"]
                ),
                "start_date": start,
                "end_date": start + timedelta(days=21),
                "target_segment": random.choice(
                    ["Mass Market", "Affluent", "Premium", "Business"]
                ),
                "budget": 25000 + idx * 5000,
                "impressions": 50000 + idx * 8000,
                "clicks": 2000 + idx * 300,
                "conversions": 120 + idx * 20,
                "cost_per_acquisition": round(90 + idx * 5, 2),
                "roi": round(0.8 + idx * 0.15, 2),
                "product_promoted": random.randint(1, 6),
                "created_at": dt(idx),
                "load_time": LOAD_TIME,
            }
        )
    return rows


def build_loan_payments(
    accounts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    payment_id = 1
    for account in accounts:
        if account["product_id"] not in {4, 5}:
            continue
        for month_offset in range(3):
            scheduled = date(2025, month_offset + 1, 12)
            actual = scheduled + timedelta(days=month_offset % 2)
            rows.append(
                {
                    "payment_id": payment_id,
                    "account_id": account["account_id"],
                    "customer_id": account["customer_id"],
                    "scheduled_date": scheduled,
                    "actual_date": actual,
                    "scheduled_amount": 650.00,
                    "actual_amount": 650.00 if month_offset != 2 else 600.00,
                    "is_late": month_offset % 2 == 1,
                    "days_late": month_offset % 2,
                    "late_fee": 25.00 if month_offset % 2 == 1 else 0.00,
                    "payment_method": random.choice(
                        ["ACH", "Check", "Online"]
                    ),
                    "outstanding_balance": abs(account["current_balance"])
                    - payment_id * 100,
                    "created_at": dt(month_offset),
                    "load_time": LOAD_TIME,
                }
            )
            payment_id += 1
    return rows


def build_branch_locations() -> list[dict[str, Any]]:
    rows = []
    for idx, (city, state, region, lat, lng) in enumerate(GEO[:5], start=1):
        rows.append(
            {
                "branch_id": idx,
                "branch_name": f"{city} Branch",
                "branch_code": f"BR{idx:05d}",
                "branch_type": random.choice(
                    ["Full Service", "Limited Service", "Commercial"]
                ),
                "address": f"{200 + idx} Finance Ave",
                "city": city,
                "state": state,
                "zip_code": f"{20000 + idx}",
                "country": "USA",
                "latitude": lat,
                "longitude": lng,
                "phone": f"555100{idx:04d}",
                "open_date": date(2015 + idx, 1, 15),
                "is_active": idx != 5,
                "square_footage": 2500 + idx * 200,
                "num_employees": 10 + idx,
                "avg_daily_customers": 120 + idx * 15,
                "has_safe_deposit": idx % 2 == 0,
                "has_notary": True,
                "has_coin_counter": idx % 3 == 0,
                "wheelchair_accessible": True,
                "operating_hours": "9AM-5PM Mon-Fri",
                "manager_name": f"Manager {idx}",
                "region": region,
                "created_at": dt(idx),
                "load_time": LOAD_TIME,
            }
        )
    return rows


def build_atm_locations(
    branches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for idx in range(1, 9):
        city, state, _, lat, lng = GEO[idx % len(GEO)]
        branch = branches[(idx - 1) % len(branches)]
        rows.append(
            {
                "atm_id": idx,
                "atm_code": f"ATM{idx:06d}",
                "location_name": f"{city} ATM {idx}",
                "location_type": random.choice(
                    ["Branch", "Off-Site", "Third-Party"]
                ),
                "address": f"{300 + idx} Cash Rd",
                "city": city,
                "state": state,
                "zip_code": f"{30000 + idx}",
                "country": "USA",
                "latitude": lat,
                "longitude": lng,
                "install_date": date(2019, (idx % 12) + 1, 10),
                "is_operational": idx != 7,
                "is_deposit_enabled": idx % 2 == 0,
                "is_cash_only": idx % 4 == 0,
                "max_withdrawal_amount": random.choice([300, 500, 800]),
                "daily_transaction_limit": 20 + idx,
                "avg_daily_transactions": 45 + idx * 3,
                "cash_capacity": 75000 + idx * 5000,
                "last_refill_date": date(2025, 1, min(20, idx + 5)),
                "last_maintenance_date": date(2024, 12, min(28, idx + 10)),
                "surcharge_fee": round(random.choice([0.0, 1.5, 2.5]), 2),
                "is_24_hour": idx % 3 != 0,
                "has_camera": True,
                "branch_id": branch["branch_id"] if idx % 2 == 0 else None,
                "created_at": dt(idx),
                "load_time": LOAD_TIME,
            }
        )
    return rows


def build_risk_assessments(
    customers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for idx, customer in enumerate(customers, start=1):
        rows.append(
            {
                "assessment_id": idx,
                "customer_id": customer["customer_id"],
                "assessment_date": date(2025, 1, min(20, idx + 1)),
                "assessment_type": random.choice(
                    [
                        "Periodic Review",
                        "Annual Review",
                        "Transaction Triggered",
                    ]
                ),
                "risk_rating": customer["risk_segment"],
                "risk_score": round(random.uniform(0.15, 0.88), 3),
                "credit_risk": random.choice(["Low", "Medium", "High"]),
                "fraud_risk": random.choice(["Low", "Medium", "High"]),
                "aml_risk": random.choice(
                    ["Low", "Medium", "High", "Critical"]
                ),
                "kyc_status": random.choice(
                    ["Verified", "Pending", "Expired"]
                ),
                "kyc_last_updated": date(2024, 12, min(25, idx + 3)),
                "pep_flag": idx % 10 == 0,
                "sanctions_flag": False,
                "adverse_media_flag": idx % 7 == 0,
                "high_value_customer": customer["customer_lifetime_value"]
                > 20000,
                "transaction_volume_last_90d": round(5000 + idx * 750, 2),
                "num_accounts": 2 if customer["customer_id"] % 2 == 0 else 1,
                "years_as_customer": round(1.5 + idx * 0.2, 2),
                "employment_verified": True,
                "income_verified": idx % 4 != 0,
                "address_verified": True,
                "regulatory_concerns": None,
                "next_review_date": date(2025, 7, min(20, idx + 1)),
                "assessor_id": f"ASSR{idx:04d}",
                "assessment_notes": f"Assessment for customer {customer['customer_id']}",
                "requires_enhanced_due_diligence": idx % 5 == 0,
                "created_at": dt(idx),
                "load_time": LOAD_TIME,
            }
        )
    return rows


def build_account_events(
    accounts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for idx, account in enumerate(accounts, start=1):
        rows.append(
            {
                "event_id": idx,
                "account_id": account["account_id"],
                "customer_id": account["customer_id"],
                "product_id": account["product_id"],
                "event_date": dt(idx % 10, 11),
                "event_type": random.choice(
                    [
                        "Account Opened",
                        "Credit Limit Increased",
                        "Fees Waived",
                        "Dormancy Warning",
                    ]
                ),
                "event_category": random.choice(
                    [
                        "Account Setup",
                        "Terms Change",
                        "Fee Related",
                        "Activity Status",
                    ]
                ),
                "old_value": "1000",
                "new_value": "1500",
                "triggered_by": random.choice(
                    ["Customer Request", "System Automated", "Risk Management"]
                ),
                "channel": random.choice(
                    ["Online", "Mobile", "Branch", "System"]
                ),
                "processed_by": f"EMP{idx:04d}",
                "notes": f"Event for account {account['account_id']}",
                "is_reversible": idx % 2 == 0,
                "requires_approval": idx % 3 == 0,
                "approval_status": random.choice(
                    ["Approved", "Pending", "Rejected"]
                )
                if idx % 3 == 0
                else None,
                "load_time": LOAD_TIME,
            }
        )
    return rows


def build_regulatory_reports(
    customers: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    report_types = [
        ("SAR", "Suspicious Activity Report", "As Needed", "FinCEN"),
        ("CTR", "Currency Transaction Report", "As Needed", "FinCEN"),
        ("AML", "Anti-Money Laundering Report", "Monthly", "FinCEN"),
        ("FFIEC", "Call Report", "Quarterly", "FFIEC"),
    ]
    for idx in range(1, 9):
        rt = report_types[(idx - 1) % len(report_types)]
        customer = customers[(idx - 1) % len(customers)]
        account = accounts[(idx - 1) % len(accounts)]
        tx = transactions[(idx * 2) % len(transactions)]
        filing_date = date(2025, 1, min(25, idx + 2))
        rows.append(
            {
                "report_id": idx,
                "report_type_code": rt[0],
                "report_type_name": rt[1],
                "report_period_start": date(2024, 10, 1),
                "report_period_end": date(2024, 12, 31),
                "filing_date": filing_date,
                "due_date": filing_date + timedelta(days=20),
                "actual_filing_date": filing_date + timedelta(days=idx % 3),
                "filing_status": random.choice(
                    ["Filed", "Pending", "Late Filed", "In Review"]
                ),
                "report_frequency": rt[2],
                "regulator": rt[3],
                "customer_id": customer["customer_id"],
                "account_id": account["account_id"],
                "transaction_id": tx["transaction_id"],
                "amount_reported": round(10000 + idx * 2500, 2),
                "risk_level": random.choice(
                    ["Low", "Medium", "High", "Critical"]
                ),
                "requires_follow_up": idx % 3 == 0,
                "follow_up_date": filing_date + timedelta(days=45),
                "assigned_to": f"COMP{idx:03d}",
                "reviewed_by": f"COMP{idx + 10:03d}",
                "approval_date": filing_date + timedelta(days=2),
                "filing_method": random.choice(["Electronic", "Paper"]),
                "confirmation_number": f"CONF{idx:06d}",
                "findings": random.choice(
                    [
                        "No Issues Found",
                        "Requires Additional Review",
                        "Discrepancy Noted",
                    ]
                ),
                "internal_notes": f"Compliance review {idx}",
                "is_amended": idx == 7,
                "original_report_id": 2 if idx == 7 else None,
                "penalty_amount": 750.00 if idx == 5 else None,
                "load_time": LOAD_TIME,
            }
        )
    return rows


def build_customer_segments_history(
    customers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    row_id = 1
    for customer in customers:
        first_date = customer["signup_date"]
        second_date = date(2024, 12, min(20, customer["customer_id"] + 5))
        rows.append(
            {
                "segment_history_id": row_id,
                "customer_id": customer["customer_id"],
                "effective_date": first_date,
                "end_date": second_date,
                "is_current": False,
                "customer_segment": "Mass Market",
                "previous_segment": None,
                "loyalty_tier": "Bronze",
                "previous_tier": None,
                "risk_segment": "Medium",
                "previous_risk": None,
                "change_type": "Segment Change",
                "change_reason": "Initial Classification",
                "triggered_by": "Automated Rule",
                "total_accounts": 1,
                "total_balance": round(
                    5000 + customer["customer_id"] * 300, 2
                ),
                "avg_monthly_transactions": 12 + customer["customer_id"],
                "products_held": 1,
                "customer_lifetime_value": customer["customer_lifetime_value"]
                * 0.7,
                "tenure_days": 180,
                "credit_score": customer["credit_score"] - 20,
                "annual_income": customer["annual_income"],
                "last_interaction_days": 30,
                "digital_engagement_score": 0.45,
                "branch_visits_last_90d": 2,
                "online_logins_last_90d": 15,
                "eligible_for_premium": False,
                "churn_risk": "Medium",
                "cross_sell_opportunity": True,
                "notes": "Initial segment assignment",
                "updated_by": "SYS100",
                "load_time": LOAD_TIME,
            }
        )
        row_id += 1
        rows.append(
            {
                "segment_history_id": row_id,
                "customer_id": customer["customer_id"],
                "effective_date": second_date,
                "end_date": None,
                "is_current": True,
                "customer_segment": customer["customer_segment"],
                "previous_segment": "Mass Market",
                "loyalty_tier": customer["loyalty_tier"],
                "previous_tier": "Bronze",
                "risk_segment": customer["risk_segment"],
                "previous_risk": "Medium",
                "change_type": "Multiple Changes",
                "change_reason": "Periodic Review",
                "triggered_by": "Risk Assessment",
                "total_accounts": 2 if customer["customer_id"] % 2 == 0 else 1,
                "total_balance": round(
                    9000 + customer["customer_id"] * 450, 2
                ),
                "avg_monthly_transactions": 20 + customer["customer_id"],
                "products_held": 2 if customer["customer_id"] % 2 == 0 else 1,
                "customer_lifetime_value": customer["customer_lifetime_value"],
                "tenure_days": 360,
                "credit_score": customer["credit_score"],
                "annual_income": customer["annual_income"],
                "last_interaction_days": 12,
                "digital_engagement_score": 0.72,
                "branch_visits_last_90d": 1,
                "online_logins_last_90d": 24,
                "eligible_for_premium": customer["customer_segment"]
                in {"Affluent", "Premium", "Business"},
                "churn_risk": random.choice(["Low", "Medium", "High"]),
                "cross_sell_opportunity": customer["customer_id"] % 3 == 0,
                "notes": "Updated segment assignment",
                "updated_by": "SYS200",
                "load_time": LOAD_TIME,
            }
        )
        row_id += 1
    return rows


def main() -> None:
    columns = load_source_columns()

    products = build_products()
    merchants = build_merchants()
    customers = build_customers()
    accounts = build_accounts(customers, products)
    transactions = build_transactions(accounts, merchants)
    credit_applications = build_credit_applications(customers)
    fraud_alerts = build_fraud_alerts(transactions)
    customer_interactions = build_customer_interactions(customers)
    economic_indicators = build_economic_indicators()
    marketing_campaigns = build_marketing_campaigns()
    loan_payments = build_loan_payments(accounts)
    branch_locations = build_branch_locations()
    atm_locations = build_atm_locations(branch_locations)
    risk_assessments = build_risk_assessments(customers)
    account_events = build_account_events(accounts)
    regulatory_reports = build_regulatory_reports(
        customers, accounts, transactions
    )
    customer_segments_history = build_customer_segments_history(customers)

    datasets = {
        "products": products,
        "merchants": merchants,
        "customers": customers,
        "accounts": accounts,
        "transactions": transactions,
        "credit_applications": credit_applications,
        "fraud_alerts": fraud_alerts,
        "customer_interactions": customer_interactions,
        "economic_indicators": economic_indicators,
        "marketing_campaigns": marketing_campaigns,
        "loan_payments": loan_payments,
        "branch_locations": branch_locations,
        "atm_locations": atm_locations,
        "risk_assessments": risk_assessments,
        "account_events": account_events,
        "regulatory_reports": regulatory_reports,
        "customer_segments_history": customer_segments_history,
    }

    ODS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for table_name, rows in datasets.items():
        sql = render_insert(table_name, columns[table_name], rows)
        (ODS_DATA_DIR / f"ods_{table_name}.sql").write_text(
            sql, encoding=TEXT_ENCODING
        )


if __name__ == "__main__":
    main()
