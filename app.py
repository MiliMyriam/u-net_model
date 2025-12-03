from flask import Flask, request, jsonify
import requests
import time

# Import your verification logic from the second script
from verification_api import verify_report   # <-- this now uses your long code

app = Flask(__name__)

@app.route('/api/verify', methods=['POST'])
def verify_report_endpoint():
    """
    Testable endpoint: send JSON to this URL → runs satellite model → returns result.
    """

    # Get JSON body
    data = request.get_json(force=True)

    try:
        report_id = data.get('reportId')
        report_type = data.get('type')
        longitude = data.get('longitude')
        latitude = data.get('latitude')
        callback_url = data.get('callbackUrl', None)  # now optional for testing

        if not all([report_id, report_type, longitude, latitude]):
            raise ValueError("Missing required fields (reportId, type, longitude, latitude)")

    except Exception as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400

    # Run the satellite verification algorithm
    verification_result = verify_report(
        report_id=report_id,
        report_type=report_type,
        lat=latitude,
        lon=longitude,
        percentage_threshold=3.0  
    )

    # If a callback URL was provided → send result back
    if callback_url:
        try:
            requests.post(callback_url, json=verification_result)
            print(f"Webhook callback sent → {callback_url}")
        except Exception as e:
            print(f"Callback error → {e}")

    # Return the result directly (for testing)
    return jsonify({
        "message": "Verification completed",
        "result": verification_result
    }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
