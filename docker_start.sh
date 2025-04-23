#!/bin/bash

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please create one based on .env.example"
    exit 1
fi

# Start the Docker Compose services
echo "Starting Deepseek Local RAG Agent services..."
docker-compose up -d

# Wait for services to start
echo "Waiting for services to start..."
sleep 5

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "Services started successfully!"
    echo "Streamlit app is available at: http://localhost:8501"
    echo "Google Drive Picker is available at: http://localhost:3001"
else
    echo "Error: Some services failed to start. Check logs with 'docker-compose logs'"
    exit 1
fi
