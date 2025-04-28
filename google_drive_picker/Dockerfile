FROM node:16-slim

WORKDIR /app

# Copy package.json and package-lock.json
COPY google_drive_picker/frontend/package*.json ./

# Install dependencies with legacy OpenSSL provider for Node.js compatibility
ENV NODE_OPTIONS=--openssl-legacy-provider
RUN npm install

# Copy the rest of the frontend code
COPY google_drive_picker/frontend/ ./

# Build the React app
RUN npm run build

# Install Python for serving the picker
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Copy the Python server file
COPY serve_picker.py ./
COPY google_drive_popup.html ./

# Install Python dependencies
RUN pip3 install flask argparse webbrowser

# Expose port for the picker server
EXPOSE 3001

# Command to run the server
CMD ["python3", "serve_picker.py", "--serve-only", "--port", "3001", "--host", "0.0.0.0"]
