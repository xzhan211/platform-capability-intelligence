from flask import Flask, jsonify
from reporting_service.http.custom_session import get_session

app = Flask(__name__)
_session = get_session()


@app.route("/reports/<report_id>")
def get_report(report_id: str):
    resp = _session.get(f"https://data-warehouse.internal/reports/{report_id}")
    return jsonify(resp.json())
