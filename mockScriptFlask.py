import os
import json
import time
import requests
from azure.servicebus import ServiceBusClient, ServiceBusReceiveMode
from verification_api import verify_report  # Keep your existing logic file!

# 1. Get Configuration from Environment Variables (We set these in Azure Portal)
CONNECTION_STR = os.environ.get("SB_CONNECTION_STRING")
QUEUE_NAME = os.environ.get("QUEUE_NAME")

if not CONNECTION_STR or not QUEUE_NAME:
    print("❌ Error: Missing Environment Variables (SB_CONNECTION_STRING or QUEUE_NAME)")
    exit(1)

def process_message(msg):
    """
    This function takes 1 message from the queue and processes it.
    """
    print(f"📥 Received message: {msg}")
    
    try:
        # A. Parse the Queue Message
        body_str = str(msg)
        data = json.loads(body_str)
        
        report_id = data.get('reportId')
        report_type = data.get('type')
        longitude = data.get('longitude')
        latitude = data.get('latitude')
        webhook_url = data.get('callbackUrl') # .NET must send this!

        print(f"   Processing Report ID: {report_id} | Type: {report_type}")

        # B. Run the Verification Logic (Same as before)
        try:
            result = verify_report(
                report_id=report_id,
                report_type=report_type, 
                lat=float(latitude),
                lon=float(longitude),
                percentage_threshold=3.0
            )
        except Exception as e:
            print(f"   ❌ Logic Error: {e}")
            return # Don't crash, just skip

        # C. Prepare the Result
        webhook_payload = {
            "reportId": result["report_id"],
            "isVerified": result["verified"],
            "timestamp": time.time(),
            "message": result["message"]
        }

        # D. Send Result back to .NET (Using Webhook)
        if webhook_url:
            print(f"   📤 Sending result to: {webhook_url}")
            try:
                # We retry 3 times just in case .NET is blinking
                for i in range(3):
                    response = requests.post(webhook_url, json=webhook_payload, timeout=10)
                    if response.status_code == 200:
                        break
                    time.sleep(1)
            except Exception as e:
                print(f"   ⚠️ Webhook failed: {e}")
        else:
            print("   ⚠️ No callbackUrl provided in message.")

    except json.JSONDecodeError:
        print("   ❌ Error: Message was not valid JSON.")
    except Exception as e:
        print(f"   ❌ Unknown Error: {e}")

# ===============================================
# Main Worker Loop
# ===============================================
if __name__ == '__main__':
    print(f"🚀 AI Worker Started. Listening to: {QUEUE_NAME}")
    
    # Create the Client
    servicebus_client = ServiceBusClient.from_connection_string(conn_str=CONNECTION_STR, logging_enable=True)

    with servicebus_client:
        # Get the Receiver
        receiver = servicebus_client.get_queue_receiver(queue_name=QUEUE_NAME)
        
        with receiver:
            # Keep running forever
            for msg in receiver:
                # 1. Process the message
                process_message(msg)
                
                # 2. Tell Azure: "I finished this message, delete it from queue"
                receiver.complete_message(msg)
                
                # Note: If Scale to Zero is on, and queue is empty, 
                # Azure will kill this container automatically after a while.
