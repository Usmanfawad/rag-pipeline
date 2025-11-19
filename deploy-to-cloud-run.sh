#!/bin/bash

# Script to push Docker image to Google Cloud and deploy to Cloud Run
# Usage: ./deploy-to-cloud-run.sh [PROJECT_ID] [REGION] [SERVICE_NAME]

set -e

# Configuration - Update these values
PROJECT_ID=${1:-"your-project-id"}  # Your GCP Project ID
REGION=${2:-"us-central1"}          # Your preferred region
SERVICE_NAME=${3:-"rag-pipeline"}   # Cloud Run service name
IMAGE_NAME="rag-pipeline"

# Choose registry (gcr.io for Container Registry or REGION-docker.pkg.dev for Artifact Registry)
# For Artifact Registry (recommended):
REGISTRY="${REGION}-docker.pkg.dev"
REPOSITORY="rag-pipeline-repo"  # Create this repository in Artifact Registry first

# For Container Registry (legacy):
# REGISTRY="gcr.io"
# REPOSITORY=""  # Leave empty for Container Registry

echo "🚀 Starting deployment to Google Cloud Run..."
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Service Name: $SERVICE_NAME"
echo ""

# Step 1: Authenticate with Google Cloud
echo "📋 Step 1: Authenticating with Google Cloud..."
gcloud auth login
gcloud config set project $PROJECT_ID

# Step 2: Configure Docker to use gcloud as credential helper
echo ""
echo "📋 Step 2: Configuring Docker credentials..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Step 3: Tag the image for Google Cloud Registry
FULL_IMAGE_NAME="${REGISTRY}/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest"
echo ""
echo "📋 Step 3: Tagging image as ${FULL_IMAGE_NAME}..."
docker tag rag-pipeline-test:latest ${FULL_IMAGE_NAME}

# Step 4: Push the image
echo ""
echo "📋 Step 4: Pushing image to Google Cloud Registry..."
docker push ${FULL_IMAGE_NAME}

echo ""
echo "✅ Image pushed successfully!"
echo ""
echo "📋 Step 5: Deploying to Cloud Run..."
echo ""

# Step 5: Deploy to Cloud Run
gcloud run deploy ${SERVICE_NAME} \
  --image ${FULL_IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --set-env-vars "PYTHONUNBUFFERED=1" \
  --set-secrets "OPENAI_API_KEY=openai-api-key:latest,PINECONE_API_KEY=pinecone-api-key:latest,JWT_SECRET_KEY=jwt-secret-key:latest"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "To update environment variables or secrets, use:"
echo "  gcloud run services update ${SERVICE_NAME} --region ${REGION} --update-env-vars KEY=VALUE"
echo ""
echo "To view logs:"
echo "  gcloud run services logs read ${SERVICE_NAME} --region ${REGION}"

