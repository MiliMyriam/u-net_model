# 1. Use Python 3.10
FROM python:3.10-slim

# 2. Set the folder
WORKDIR /app

# 3. Install system libraries (including the libgl1 fix)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 5. Copy the code
COPY . .

# 6. Run the Worker (NOT the API)
CMD ["python", "worker.py"]
