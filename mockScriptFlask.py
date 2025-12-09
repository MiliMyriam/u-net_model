from flask import Flask, request, jsonify
import requests
import time

# Import the logic from the previous file (saved as verification_api.py)
from verification_api import verify_report

app = Flask(__name__)

# ===============================================
# Primary API Endpoint
# ===============================================
@app.route('/api/verify', methods=['POST'])
def verify_report_endpoint():
    """
    API endpoint that receives a report, calls the verification logic,
    and sends the result to a webhook.
    """
    
    # 1. Parse Request
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Empty request body"}), 400
            
        report_id = data.get('reportId')
        report_type = data.get('type')
        longitude = data.get('longitude')
        latitude = data.get('latitude')
        webhook_url = data.get('callbackUrl')

        # Basic Validation
        if not all([report_id, report_type, longitude, latitude, webhook_url]):
            return jsonify({"error": "Missing required fields"}), 400

        # Validate Coordinates
        if not (-90 <= float(latitude) <= 90 and -180 <= float(longitude) <= 180):
            return jsonify({"error": "Invalid coordinates"}), 400

    except Exception as e:
        return jsonify({"error": f"Request parsing error: {str(e)}"}), 400

    # 2. Call Verification Logic
    # We pass the raw report_type. The verify_report function handles:
    # - Checking if it's Danger/Medical (returns verified=False, status=200)
    # - Checking if it's Shelter/Resource (runs satellite model)
    # - Checking if it's Invalid (returns status=400)
    try:
        result = verify_report(
            report_id=report_id,
            report_type=report_type, 
            lat=float(latitude),
            lon=float(longitude),
            percentage_threshold=3.0
        )
    except Exception as e:
        print(f"❌ Internal Error: {e}")
        return jsonify({"error": "Internal verification error"}), 500

    # 3. Handle Logic Result
    
    # If the logic says the input was bad (e.g., type="UFO"), return 400
    if result.get("status") == 400:
        return jsonify({"error": result.get("message")}), 400
        
    # If the logic failed internally (e.g., screenshot error), return 500
    if result.get("status") == 500:
        return jsonify({"error": result.get("message")}), 500

    # 4. Success (Status 200) - Send Webhook
    # This covers both:
    # - Verified Satellite matches (verified=True)
    # - Danger/Medical reports (verified=False, but successful processing)
    
    webhook_payload = {
        "reportId": result["report_id"],
        "isVerified": result["verified"], # False for Danger/Medical, True/False for others
        "timestamp": time.time(),
        "message": result["message"]
    }

    print(f"📤 Sending webhook to {webhook_url} | Payload: {webhook_payload}")

    try:
        # Send webhook (Fire and forget, or wait for response)
        requests.post(webhook_url, json=webhook_payload, timeout=5)
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Webhook failed: {e}")
        # We still return 200 to the caller because WE processed it successfully,
        # even if the callback server is down.

    return jsonify({
        "message": "Report processed successfully",
        "reportId": result["report_id"],
        "isVerified": result["verified"]
    }), 200

# ===============================================
# Run
# ===============================================
if __name__ == '__main__':
    print("🚀 API Server Running on Port 5000...")
    app.run(host='0.0.0.0', port=5000)
