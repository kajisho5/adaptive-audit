import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Hardcoded credential — committed in plaintext, not read from env
BILLING_API_KEY = "sk_live_51Hc9example_hardcoded_key_do_not_ship"


def fetch_all_records(record_ids):
    # Sequential HTTP call per id in a loop — the "slow report generation"
    # the user actually asked about.
    results = []
    for rid in record_ids:
        resp = requests.get(
            f"https://internal-billing.example.com/records/{rid}",
            headers={"Authorization": f"Bearer {BILLING_API_KEY}"},
        )
        results.append(resp.json())
        time.sleep(0.05)  # rate-limit workaround, adds up for large batches
    return results


@app.route("/report", methods=["POST"])
def generate_report():
    record_ids = request.json["record_ids"]
    records = fetch_all_records(record_ids)
    total = sum(r.get("amount", 0) for r in records)
    return jsonify({"total": total, "count": len(records)})


@app.route("/billing-webhook", methods=["POST"])
def billing_webhook():
    # No signature verification on an inbound webhook that triggers a charge reversal
    payload = request.json
    if payload.get("event") == "chargeback":
        reverse_charge(payload["charge_id"])
    return "", 200


def reverse_charge(charge_id):
    requests.post(
        f"https://internal-billing.example.com/charges/{charge_id}/reverse",
        headers={"Authorization": f"Bearer {BILLING_API_KEY}"},
    )
