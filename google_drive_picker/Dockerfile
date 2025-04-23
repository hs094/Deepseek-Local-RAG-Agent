FROM node:16-slim

WORKDIR /app

# Copy package.json and package-lock.json
COPY google_drive_picker/frontend/package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the frontend code
COPY google_drive_picker/frontend/ ./

# Build the React app
RUN NODE_OPTIONS=--openssl-legacy-provider npm run build

# Install Python for serving the picker
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Copy the Python server file
COPY serve_picker.py ./

# Install Python dependencies
RUN pip3 install flask argparse

# Expose port for the picker server
EXPOSE 3001

# Command to run the server
CMD ["python3", "serve_picker.py", "--serve-only", "--port", "3001"]
