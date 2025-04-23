#!/bin/bash

# Stop the Docker Compose services
echo "Stopping Deepseek Local RAG Agent services..."
docker-compose down

# Check if services are stopped
if docker-compose ps | grep -q "Exit\|Up"; then
    echo "Error: Some services failed to stop. Check with 'docker-compose ps'"
    exit 1
else
    echo "Services stopped successfully!"
fi
