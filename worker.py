import os
import json
import time
import requests
from azure.servicebus import ServiceBusClient
from verification_api import verify_report 

# 1. Get Configuration from Environment Variables
CONNECTION_STR = os.environ.get("SB_CONNECTION_STRING")
QUEUE_NAME = os.environ.get("QUEUE_NAME")

if not CONNECTION_STR or not QUEUE_NAME:
    print("❌ Error: Missing Environment Variables (SB_CONNECTION_STRING or QUEUE_NAME)")
    exit(1)

def process_message(msg):
    print(f"📥 Received message: {msg}")
    try:
        body_str = str(msg)
        data = json.loads(body_str)
        
        report_id = data.get('reportId')
        report_type = data.get('type')
        longitude = float(data.get('longitude', 0))
        latitude = float(data.get('latitude', 0))
        webhook_url = data.get('callbackUrl')

        print(f"   Processing Report ID: {report_id} | Type: {report_type}")

        # Run Verification Logic
        try:
            result = verify_report(
                report_id=report_id,
                report_type=report_type, 
                lat=latitude,
                lon=longitude,
                percentage_threshold=3.0
            )
        except Exception as e:
            print(f"   ❌ Logic Error: {e}")
            return

        webhook_payload = {
            "reportId": result["report_id"],
            "isVerified": result["verified"],
            "timestamp": time.time(),
            "message": result["message"]
        }

        if webhook_url:
            print(f"   📤 Sending result to: {webhook_url}")
            try:
                # Retry loop
                for i in range(3):
                    response = requests.post(webhook_url, json=webhook_payload, timeout=10)
                    if response.status_code == 200:
                        break
                    time.sleep(1)
            except Exception as e:
                print(f"   ⚠️ Webhook failed: {e}")
        else:
            print("   ⚠️ No callbackUrl provided.")

    except Exception as e:
        print(f"   ❌ Unknown Error: {e}")

# Main Worker Loop
if __name__ == '__main__':
    print(f"🚀 AI Worker Started. Listening to: {QUEUE_NAME}")
    servicebus_client = ServiceBusClient.from_connection_string(conn_str=CONNECTION_STR, logging_enable=True)

    with servicebus_client:
        receiver = servicebus_client.get_queue_receiver(queue_name=QUEUE_NAME)
        with receiver:
            for msg in receiver:
                process_message(msg)
                receiver.complete_message(msg)
