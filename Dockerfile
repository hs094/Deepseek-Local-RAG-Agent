FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Fix dependency conflicts and install Python dependencies
RUN pip install --no-cache-dir pip==24.0 && \
    # Fix the protobuf version conflict
    sed -i 's/protobuf==6.30.2/protobuf==5.26.1/g' requirements.txt && \
    # Install dependencies
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port for Streamlit
EXPOSE 8501

# Command to run the application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
