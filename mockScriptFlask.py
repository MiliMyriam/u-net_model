from flask import Flask, request, jsonify
import requests
import time

# Import your verification logic
from verification_api import verify_report

# If you want to support a health check later:
model_load_error = None

# Valid input types that the backend may send
VALID_REPORT_TYPES = ["water", "vegetation", "shelter"]

# Mapping of input → internal model type
TYPE_MAPPING = {
    "water": "water",
    "vegetation": "vegetation",
    "shelter": "building"   # Treat "shelter" as "building"
}

# Initialize the Flask App
app = Flask(__name__)


# -----------------------------------------------
# Primary API Endpoint (Webhook Listener)
# -----------------------------------------------
@app.route('/api/verify', methods=['POST'])
def verify_report_endpoint():
    """API endpoint for satellite verification."""
    
    data = request.get_json(force=True)

    try:
        report_id = data.get('reportId')
        report_type = data.get('type')
        longitude = data.get('longitude')
        latitude = data.get('latitude')
        webhook_url = data.get('callbackUrl')

        # Required fields
        if not all([report_id, report_type, longitude, latitude, webhook_url]):
            raise ValueError("Missing required fields (reportId, type, longitude, latitude, callbackUrl)")

        # Normalize type
        report_type = report_type.lower()

        # Validate user-visible types
        if report_type not in VALID_REPORT_TYPES:
            raise ValueError(f"Invalid report type: {report_type}. Valid types: {VALID_REPORT_TYPES}")

        # Convert to internal type
        mapped_type = TYPE_MAPPING[report_type]

        # Validate coordinates
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("Invalid coordinates: latitude must be -90 to 90, longitude must be -180 to 180")

    except ValueError as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400
    except Exception as e:
        return jsonify({"error": f"Request parsing error: {e}"}), 400

    # Run the model
    try:
        verification_result = verify_report(
            report_id=report_id,
            report_type=mapped_type,
            lat=latitude,
            lon=longitude,
            percentage_threshold=3.0
        )
    except Exception as e:
        print(f"❌ Verification error for {report_id}: {e}")
        return jsonify({"error": f"Verification failed: {e}"}), 500

    # Prepare webhook payload
    result_payload = {
        "reportId": verification_result["report_id"],
        "isVerified": verification_result["verified"],
        "timestamp": time.time()
    }

    # Send webhook
    try:
        response = requests.post(webhook_url, json=result_payload, timeout=10)
        response.raise_for_status()
        print(f"✅ Sent result to webhook: {webhook_url}")
    except requests.exceptions.Timeout:
        print(f"⚠️ WARNING: Webhook timeout for {webhook_url}")
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Failed to send webhook to {webhook_url}: {e}")

    # Return API response
    return jsonify({
        "message": f"Verification for {report_id} completed",
        "reportId": report_id,
        "isVerified": verification_result["verified"]
    }), 200


# -----------------------------------------------
# Error Handlers
# -----------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500


# -----------------------------------------------
# Run the application
# -----------------------------------------------
if __name__ == '__main__':
    print("🛰️  Starting Satellite Report Verification API...")
    app.run(host='0.0.0.0', port=5000, debug=False)
