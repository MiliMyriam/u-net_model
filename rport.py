from flask import Flask, request, jsonify
import requests 
import time
from app import verify_report, model_load_error, VALID_REPORT_TYPES

# 1. Initialize the Flask App
app = Flask(__name__)

# -----------------------------------------------

# 2. Health Check Endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Check if the satellite model is loaded and API is ready."""
    if model_load_error:
        return jsonify({"status": "error", "message": f"Model not loaded: {model_load_error}"}), 503
    return jsonify({"status": "ok", "message": "Satellite verification service is ready"}), 200

# -----------------------------------------------

# 3. Primary API Endpoint (Webhook Listener)
@app.route('/api/verify', methods=['POST'])
def verify_report_endpoint():
    """
    Receives a report from the C# backend, runs the satellite verification,
    and sends the result back to the C# backend's callback URL.
    """
    
    # 3.1 Check if model is loaded
    if model_load_error:
        return jsonify({"error": f"Model not available: {model_load_error}"}), 503
    
    # 3.2 Get the JSON data from the C# backend
    data = request.get_json(force=True)
    
    # 3.3 Extract and validate required fields
    try:
        report_id = data.get('reportId')
        report_type = data.get('type')
        longitude = data.get('longitude')
        latitude = data.get('latitude')
        webhook_url = data.get('callbackUrl')
        
        # Validation for required fields
        if not all([report_id, report_type, longitude, latitude, webhook_url]):
            raise ValueError("Missing required fields (reportId, type, longitude, latitude, callbackUrl)")
        
        # Validate report type
        if report_type.lower() not in VALID_REPORT_TYPES:
            raise ValueError(f"Invalid report type: {report_type}. Valid types: {VALID_REPORT_TYPES}")
        
        # Validate coordinates
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("Invalid coordinates: latitude must be -90 to 90, longitude must be -180 to 180")

    except ValueError as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400
    except Exception as e:
        return jsonify({"error": f"Request parsing error: {e}"}), 400

    # 3.4 Run the satellite verification model
    try:
        verification_result = verify_report(
            report_id=report_id,
            report_type=report_type,
            lat=latitude,
            lon=longitude,
            percentage_threshold=3.0
        )
    except Exception as e:
        print(f"❌ Verification error for {report_id}: {e}")
        return jsonify({"error": f"Verification failed: {e}"}), 500
    
    # 3.5 Prepare the result payload for the C# backend
    result_payload = {
        "reportId": verification_result["report_id"],
        "isVerified": verification_result["verified"],
        "timestamp": time.time()
    }
    
    # 3.6 Send the result back to the C# Backend's Webhook URL (async would be better in production)
    try:
        response = requests.post(webhook_url, json=result_payload, timeout=10)
        response.raise_for_status()
        print(f"✅ Sent result to webhook: {webhook_url}")
    except requests.exceptions.Timeout:
        print(f"⚠️  WARNING: Webhook timeout for {webhook_url}")
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Failed to send webhook to {webhook_url}: {e}")
        # Don't fail the API response - verification completed successfully
        
    # 3.7 Return a success response to the initial C# API caller
    return jsonify({
        "message": f"Verification for {report_id} completed",
        "reportId": report_id,
        "isVerified": verification_result["verified"]
    }), 200


# 4. Error Handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500

# 5. Run the application (Entry point)
if __name__ == '__main__':
    print("🛰️  Starting Satellite Report Verification API...")
    app.run(host='0.0.0.0', port=5000, debug=False)