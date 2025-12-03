import urllib.parse
from PIL import Image
# NOTE: Ensure 'playwright' is installed: pip install playwright
from playwright.sync_api import sync_playwright

def generate_skyfi_url(center_lat, center_lon, delta=0.02):
    """
    Generates the skyfi tasking URL with a dynamically calculated WKT POLYGON
    to define the Area of Interest (AOI).
    """
    # 1. Calculate the bounding box coordinates
    min_lon = center_lon - delta
    max_lon = center_lon + delta
    min_lat = center_lat - delta
    max_lat = center_lat + delta

    # 2. Define the four corner points (in Longitude Latitude format for WKT)
    coords = [
        (max_lon, max_lat),  # Top-Right
        (max_lon, min_lat),  # Bottom-Right
        (min_lon, min_lat),  # Bottom-Left
        (min_lon, max_lat),  # Top-Left
        (max_lon, max_lat)   # Close the polygon (back to Top-Right)
    ]
    
    # 3. Format into the WKT POLYGON string
    coord_string = ", ".join([f"{lon} {lat}" for lon, lat in coords])
    wkt_polygon = f"POLYGON (({coord_string}))"
    
    # 4. URL-encode the WKT string
    encoded_aoi = urllib.parse.quote_plus(wkt_polygon)

    # 5. Construct the final URL
    base_url = "https://app.skyfi.com/tasking"
    # Parameters: s=DAY (Sentinel-2), r=VERY HIGH (Resolution)
    final_url = f"{base_url}?s=DAY&r=VERY+HIGH&aoi={encoded_aoi}"
    
    return final_url

def capture_screenshot(url, filename="skyfi_screenshot.png", clip_region=None, crop_center=False):
    """
    Launches a headless browser, navigates to the URL, and saves a screenshot.
    If crop_center is True, crops the image to center ±100 pixels.
    """
    print("Initializing playwright...")
    try:
        with sync_playwright() as p:
            # Launch the Chromium browser
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Set a standard viewport size for consistent capture
            page.set_viewport_size({"width": 1920, "height": 1080})

            print(f"Navigating to {url}...")
            
            # Navigate to the URL and wait until network activity calms down
            page.goto(url, wait_until="networkidle", timeout=60000) # 60 second timeout

            # --- Screenshot Logic ---
            temp_filename = "skyfi_screenshot.png"
            
            if clip_region:
                # Capture only the defined clip area
                page.screenshot(path=temp_filename, clip=clip_region)
                print(f"✅ Zoomed screenshot (clipped) taken")
            else:
                # Capture the full viewport
                page.screenshot(path=temp_filename, full_page=False)
                print(f"✅ Screenshot (full viewport) taken")

            browser.close()
            
            # --- Crop Logic (center ±100 pixels) ---
            if crop_center:
                # Load the temporary screenshot
                img = Image.open(temp_filename)
                width, height = img.size
                
                # Calculate center coordinates
                center_x, center_y = width // 2, height // 2
                
                # Define crop box (center ±100 pixels)
                left = center_x - 100
                top = center_y - 100
                right = center_x + 100
                bottom = center_y + 100
                
                # Ensure crop coordinates are within image bounds
                left = max(0, left)
                top = max(0, top)
                right = min(width, right)
                bottom = min(height, bottom)
                
                # Crop the image
                cropped_img = img.crop((left, top, right, bottom))
                
                # Save the cropped image
                cropped_img.save(filename)
                print(f"✅ Center-cropped screenshot saved as {filename} (±100 pixels from center)")
                
                # Delete temporary file
                import os
                os.remove(temp_filename)
            else:
                # No cropping needed, just rename the file
                import os
                os.rename(temp_filename, filename)
                print(f"✅ Screenshot saved as {filename}")
            
    except Exception as e:
        print(f"❌ Playwright Error: {e}")
        print("Please ensure 'playwright install' has been run to download browser binaries.")
        raise # Re-raise the exception to be caught in the main application

# Example usage:
if __name__ == "__main__":
    # Example coordinates (Statue of Liberty)
    center_lat = 40.6892
    center_lon = -74.0445
    
    # Generate URL
    url = generate_skyfi_url(center_lat, center_lon)
    print(f"Generated URL: {url}")
    
    # Take screenshot with center cropping (±100 pixels)
    capture_screenshot(url, "skyfi_screenshot.png", crop_center=True)
    
