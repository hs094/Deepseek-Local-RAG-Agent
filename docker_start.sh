#!/bin/bash

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please create one based on .env.example"
    exit 1
fi

# Check if curl is installed
if ! command -v curl &> /dev/null; then
    echo "Warning: curl is not installed. It's recommended for healthchecks."
    echo "Install with: brew install curl (macOS) or apt-get install curl (Linux)"
fi

# Start the Docker Compose services
echo "Starting Deepseek Local RAG Agent services..."
docker-compose up -d

# Wait for services to start
echo "Waiting for services to start..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "Services started successfully!"

    # Check Qdrant health
    echo "Checking Qdrant health..."
    if curl -s -f http://localhost:6333/readiness &> /dev/null; then
        echo "✅ Qdrant is healthy"
    else
        echo "⚠️ Qdrant may not be fully ready yet"
    fi

    # Check Streamlit
    echo "Checking Streamlit..."
    if curl -s -f http://localhost:8501 &> /dev/null; then
        echo "✅ Streamlit is running"
    else
        echo "⚠️ Streamlit may not be fully ready yet"
    fi

    # Check Google Drive Picker
    echo "Checking Google Drive Picker..."
    if curl -s -f http://localhost:3001 &> /dev/null; then
        echo "✅ Google Drive Picker is running"
    else
        echo "⚠️ Google Drive Picker may not be fully ready yet"
    fi

    echo ""
    echo "Streamlit app is available at: http://localhost:8501"
    echo "Google Drive Picker is available at: http://localhost:3001"
    echo ""
    echo "For logs, run: docker-compose logs -f"
else
    echo "Error: Some services failed to start. Check logs with 'docker-compose logs'"
    exit 1
fi
