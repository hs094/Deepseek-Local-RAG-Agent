# Pull the Qdrant image
docker pull qdrant/qdrant

# Create a directory for persistent storage
mkdir -p ~/qdrant_storage

# Run Qdrant container
docker run -d --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v ~/qdrant_storage:/qdrant/storage \
  qdrant/qdrant