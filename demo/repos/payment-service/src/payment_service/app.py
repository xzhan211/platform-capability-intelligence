from flask import Flask, jsonify, request
from payment_service.clients.payment_gateway import PaymentGatewayClient

app = Flask(__name__)
gateway = PaymentGatewayClient()


@app.route("/payments", methods=["POST"])
def create_payment():
    data = request.json
    result = gateway.submit_payment(data)
    return jsonify(result)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})
