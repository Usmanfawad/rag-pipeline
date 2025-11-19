#!/bin/bash

# Test script for Dockerfile
set -e

echo "🔨 Building Docker image..."
docker build -t rag-pipeline-test .

echo ""
echo "✅ Build successful!"
echo ""
echo "To test the container, run:"
echo "  docker run -p 8080:8080 --env-file .env rag-pipeline-test"
echo ""
echo "Or with environment variables:"
echo "  docker run -p 8080:8080 \\"
echo "    -e PINECONE_API_KEY=your_key \\"
echo "    -e OPENAI_API_KEY=your_key \\"
echo "    -e JWT_SECRET_KEY=your_secret \\"
echo "    rag-pipeline-test"
echo ""
echo "Then visit http://localhost:8080/docs to test the API"

