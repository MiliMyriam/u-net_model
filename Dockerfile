# 1. Use Python 3.10 (Compatible with your newer libraries)
FROM python:3.10-slim

# 2. Set the folder
WORKDIR /app

# 3. CRITICAL: Install system libraries for OpenCV and EarthEngine
# Without these lines, 'opencv-python' will crash the container.
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy requirements and install
COPY requirements.txt .
# We use --upgrade to fix any version conflicts in your friend's list
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 5. Copy the code
COPY . .

# 6. Run the app
# Based on your previous file list, verification_api.py seems to be the main one.
CMD ["python", "verification_api.py"]
