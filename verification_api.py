import os
import urllib.parse
import time
import numpy as np
import tensorflow as tf
from PIL import Image
from keras.models import load_model
from keras.layers import Conv2DTranspose
from playwright.sync_api import sync_playwright

# =========================
# Custom Conv2DTranspose
# =========================
class CustomConv2DTranspose(Conv2DTranspose):
    def __init__(self, *args, **kwargs):
        kwargs.pop('groups', None)
        super().__init__(*args, **kwargs)

# =========================
# Loss Functions
# =========================
def jaccard_coef(y_true, y_pred):
    y_true_f = tf.reshape(y_true, [-1])
    y_pred_f = tf.reshape(y_pred, [-1])
    intersection = tf.reduce_sum(y_true_f * y_pred_f)
    union = tf.reduce_sum(y_true_f) + tf.reduce_sum(y_pred_f) - intersection
    return (intersection + 1.0) / (union + 1.0)

def categorical_focal_loss(weights, gamma=2.0):
    weights = tf.constant(weights, dtype=tf.float32)
    def loss(y_true, y_pred):
        y_pred = tf.clip_by_value(y_pred, 1e-8, 1.0)
        ce = -y_true * tf.math.log(y_pred)
        alpha_factor = y_true * weights
        modulating_factor = tf.pow(1.0 - y_pred, gamma)
        fl = alpha_factor * modulating_factor * ce
        return tf.reduce_mean(tf.reduce_sum(fl, axis=-1))
    return loss

# =========================
# Model Loading
# =========================
num_classes = 7
weights = [1.0 / num_classes] * num_classes
focal_loss = categorical_focal_loss(weights=weights)
custom_objects = {
    "loss": focal_loss,
    "jaccard_coef": jaccard_coef,
    "Conv2DTranspose": CustomConv2DTranspose
}

satellite_model = None
model_load_error = None

try:
    print("[INIT] Loading satellite model...")
    satellite_model = load_model(
        "model/satellite-imagery.h5",
        custom_objects=custom_objects,
        compile=False
    )
    print("[INIT] ✓ Model loaded successfully")
except FileNotFoundError:
    model_load_error = "Model file not found: model/satellite-imagery.h5"
    print(f"[INIT] ❌ {model_load_error}")
except Exception as e:
    model_load_error = str(e)
    print(f"[INIT] ❌ {model_load_error}")

# =========================
# Class Configuration
# =========================
CLASS_NAMES = [
    "Building", "Land", "Road", "Vegetation", 
    "Water", "Unlabeled", "Background"
]

VALID_REPORT_TYPES = ["Danger", "Shelter", "Resource", "MedicalNeed","Resource spot"]

CLASS_TO_REPORT_TYPE = {
    "Building": ["building"],
    "Land": ["land", "flood"],
    "Road": ["road"],
    "Vegetation": ["vegetation", "fire"],
    "Water": ["water", "flood"]
}

# =========================
# SkyFi Functions
# =========================
def generate_skyfi_url(lat, lon, delta=0.02):
    """Generate SkyFi URL with AOI polygon."""
    min_lon, max_lon = lon - delta, lon + delta
    min_lat, max_lat = lat - delta, lat + delta
    
    coords = [
        (max_lon, max_lat),
        (max_lon, min_lat),
        (min_lon, min_lat),
        (min_lon, max_lat),
        (max_lon, max_lat)
    ]
    
    coord_str = ", ".join([f"{x} {y}" for x, y in coords])
    wkt = f"POLYGON (({coord_str}))"
    encoded = urllib.parse.quote_plus(wkt)
    return f"https://app.skyfi.com/tasking?s=DAY&r=VERY+HIGH&aoi={encoded}"

def capture_screenshot(url, filename="skyfi_screenshot.png", crop_center=False):
    """Capture and save screenshot from SkyFi URL."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            temp_file = "temp_screenshot.png"
            page.screenshot(path=temp_file)
            browser.close()
            
            if crop_center:
                img = Image.open(temp_file)
                w, h = img.size
                cx, cy = w // 2, h // 2
                crop_box = (cx - 300, cy - 300, cx + 300, cy + 300)
                img.crop(crop_box).save(filename)
                os.remove(temp_file)
            else:
                os.rename(temp_file, filename)
            
            return filename
    except Exception as e:
        print(f"❌ Screenshot error: {e}")
        return None

# =========================
# Model Segmentation
# =========================
def segment_image(image_path, confidence_threshold=0.3):
    """
    Segment satellite image and return detected classes with percentages.
    
    Returns:
        tuple: (detected_classes, class_percentages)
    """
    if satellite_model is None:
        return None, None
    
    try:
        img = Image.open(image_path).convert("RGB")
        
        # Resize to model input size
        resized = img.resize((256, 256))
        img_np = np.array(resized) / 255.0
        batch = np.expand_dims(img_np, 0)
        
        # Predict
        pred = satellite_model.predict(batch, verbose=0)
        mask = np.argmax(pred, axis=-1)[0]
        conf = np.max(pred, axis=-1)[0]
        
        # Apply confidence threshold
        mask[conf < confidence_threshold] = 5
        
        # Calculate percentages
        unique, counts = np.unique(mask, return_counts=True)
        total = mask.size
        
        class_percentages = {}
        for cls_idx, count in zip(unique, counts):
            percentage = (count / total) * 100
            class_percentages[CLASS_NAMES[cls_idx]] = percentage
        
        return list(unique), class_percentages
    
    except Exception as e:
        print(f"❌ Segmentation error: {e}")
        return None, None

def check_class_match_with_threshold(detected_classes, class_percentages, report_type, threshold=3.0):
    """
    Check if detected classes match report type AND exceed threshold percentage.
    
    Returns:
        bool: True if match found with percentage > threshold
    """
    report_type = report_type.lower()
    
    for cls_idx in detected_classes:
        cls_name = CLASS_NAMES[cls_idx]
        matching_types = CLASS_TO_REPORT_TYPE.get(cls_name, [])
        
        if report_type in matching_types:
            percentage = class_percentages.get(cls_name, 0)
            if percentage > threshold:
                print(f"   ✅ Match found: {cls_name} = {percentage:.2f}% (threshold: {threshold}%)")
                return True
    
    return False

# =========================
# Main Verification Function
# =========================
def verify_report(report_id, report_type, lat, lon, confidence_threshold=0.3, percentage_threshold=3.0):
    """
    Verify a report and return report_id + boolean result.
    If report_type is 'MedicalNeed', return False by default.
    """
    
    print(f"\n🔍 Processing: {report_id}")
    
    # Validate report type
    report_type_lower = report_type.lower()
    
    if report_type_lower not in [r.lower() for r in VALID_REPORT_TYPES]:
        print(f"❌ Invalid type: {report_type}")
        return {"report_id": str(report_id), "verified": False}

    # Special logic for MedicalNeed: always return False
    if report_type_lower == "medicalneed":
        print("⚠️ Report type is MedicalNeed → automatically unverified")
        return {"report_id": str(report_id), "verified": False}
    
    # Generate SkyFi URL and capture screenshot
    skyfi_url = generate_skyfi_url(lat, lon)
    screenshot_name = f"report_{report_id}_{int(time.time())}.png"
    screenshot_path = capture_screenshot(skyfi_url, screenshot_name, crop_center=True)
    
    if not screenshot_path:
        print(f"❌ Screenshot failed")
        return {"report_id": str(report_id), "verified": False}
    
    # Segment the image
    detected_classes, class_percentages = segment_image(screenshot_path, confidence_threshold)
    
    if detected_classes is None:
        print(f"❌ Segmentation failed")
        return {"report_id": str(report_id), "verified": False}
    
    # Check if class matches and exceeds threshold
    verified = check_class_match_with_threshold(
        detected_classes, 
        class_percentages, 
        report_type, 
        percentage_threshold
    )
    
    print(f"📊 Result: {verified}")
    
    return {"report_id": str(report_id), "verified": verified}

# =========================
# Batch Processing
# =========================
def verify_batch(reports_list, percentage_threshold=3.0):
    """
    Process multiple reports.
    
    Args:
        reports_list: List of dicts with keys: report_id, report_type, lat, lon
        percentage_threshold: Minimum percentage for match
    
    Returns:
        list: List of {"report_id": str, "verified": bool}
    """
    results = []
    for report in reports_list:
        result = verify_report(
            report_id=report["report_id"],
            report_type=report["report_type"],
            lat=report["lat"],
            lon=report["lon"],
            percentage_threshold=percentage_threshold
        )
        results.append(result)
    
    return results

# =========================
# Example Usage
# =========================
if __name__ == "__main__":
    print("🛰️  Satellite Report Verification System")
    print("=" * 60)
    
    # Single report
    result = verify_report(
        report_id="FIRE-2024-001",
        report_type="fire",
        lat=40.6892,
        lon=-74.0445,
        percentage_threshold=3.0
    )
    
    print(f"\n✅ Result: {result}")
    
    # Batch processing
    test_reports = [
        {"report_id": "FIRE-001", "report_type": "fire", "lat": 40.6892, "lon": -74.0445},
        {"report_id": "FLOOD-001", "report_type": "flood", "lat": 34.0522, "lon": -118.2437},
        {"report_id": "BUILD-001", "report_type": "building", "lat": 48.8584, "lon": 2.2945},
        {"report_id": "MED-001", "report_type": "MedicalNeed", "lat": 51.5074, "lon": -0.1278}
    ]
    
    batch_results = verify_batch(test_reports, percentage_threshold=3.0)
    print(f"\n📋 Batch Results:")
    for res in batch_results:
        print(f"   {res}")
