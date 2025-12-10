import urllib.parse
from PIL import Image
# NOTE: Ensure 'playwright' is installed: pip install playwright
from playwright.sync_api import sync_playwright

def generate_skyfi_url(center_lat, center_lon, delta=0.005):
    """
    Generates the skyfi tasking URL with a dynamically calculated WKT POLYGON
    to define the Area of Interest (AOI).
    
    Reduced delta from 0.02 to 0.005 for better zooming (4x closer zoom)
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
    Launches a headless browser, navigates to the URL, and saves a high-quality screenshot.
    If crop_center is True, crops the image to center ±100 pixels.
    
    Enhanced for higher quality: 4K viewport and high-quality PNG compression
    """
    print("Initializing playwright...")
    try:
        with sync_playwright() as p:
            # Launch the Chromium browser
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Set a 4K viewport size for higher quality capture
            page.set_viewport_size({"width": 3840, "height": 2160})

            print(f"Navigating to {url}...")
            
            # Navigate to the URL and wait until network activity calms down
            page.goto(url, wait_until="networkidle", timeout=60000) # 60 second timeout

            # --- Screenshot Logic ---
            temp_filename = "skyfi_screenshot_temp.png"
            
            if clip_region:
                # Capture only the defined clip area with high quality
                page.screenshot(path=temp_filename, clip=clip_region, type='png')
                print(f"✅ Zoomed screenshot (clipped) taken in high quality")
            else:
                # Capture the full viewport with high quality
                page.screenshot(path=temp_filename, full_page=False, type='png')
                print(f"✅ Screenshot (full viewport) taken in high quality")

            browser.close()
            print("Browser closed")
            
            # --- Crop Logic (center ±100 pixels) ---
            if crop_center:
                print("Starting center crop process...")
                # Load the temporary screenshot
                img = Image.open(temp_filename)
                width, height = img.size
                print(f"Original image size: {width}x{height}")
                
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
                
                print(f"Cropping to: left={left}, top={top}, right={right}, bottom={bottom}")
                
                # Crop the image
                cropped_img = img.crop((left, top, right, bottom))
                
                # Save the cropped image with maximum quality
                cropped_img.save(filename, 'PNG', optimize=False, compress_level=0)
                print(f"✅ Center-cropped high-quality screenshot saved as {filename} (±100 pixels from center)")
                
                # Delete temporary file
                import os
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                    print(f"Temporary file {temp_filename} deleted")
            else:
                # No cropping needed, just rename the file
                import os
                if os.path.exists(filename):
                    os.remove(filename)
                os.rename(temp_filename, filename)
                print(f"✅ High-quality screenshot saved as {filename}")
            
    except Exception as e:
        print(f"❌ Playwright Error: {e}")
        print("Please ensure 'playwright install' has been run to download browser binaries.")
        import traceback
        traceback.print_exc()
        raise # Re-raise the exception to be caught in the main application

# Example usage:
if _name_ == "_main_":
    import os
    
    # Example coordinates (Statue of Liberty)
    center_lat = 40.6892
    center_lon = -74.0445
    
    # Print current working directory
    print("=" * 60)
    print(f"📁 Current working directory: {os.getcwd()}")
    print("=" * 60)
    
    # Generate URL with better zoom
    url = generate_skyfi_url(center_lat, center_lon)
    print(f"\n🌐 Generated URL: {url}\n")
    
    # Use absolute path for the screenshot
    output_path = os.path.join(os.getcwd(), "skyfi_screenshot.png")
    print(f"📁 Will save screenshot to: {output_path}\n")
    
    # Take high-quality screenshot with center cropping (±100 pixels)
    try:
        capture_screenshot(url, output_path, crop_center=True)
        
        # Verify the file exists
        print("\n" + "=" * 60)
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✅ SUCCESS! File created at:")
            print(f"   {output_path}")
            print(f"📊 File size: {file_size:,} bytes ({file_size/1024:.2f} KB)")
        else:
            print(f"❌ ERROR: File was not created at {output_path}")
        print("=" * 60)
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ ERROR during screenshot capture: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
