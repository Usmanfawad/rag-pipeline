# Deploying to Google Cloud Run

This guide will help you push your Docker image to Google Cloud and deploy it to Cloud Run.

## Prerequisites

1. **Google Cloud SDK (gcloud)** installed
   ```bash
   # Install gcloud CLI if not already installed
   # macOS:
   brew install google-cloud-sdk
   
   # Or download from: https://cloud.google.com/sdk/docs/install
   ```

2. **Docker** installed and running

3. **Google Cloud Project** created with billing enabled

4. **Required APIs enabled**:
   ```bash
   gcloud services enable run.googleapis.com
   gcloud services enable containerregistry.googleapis.com  # For Container Registry
   # OR
   gcloud services enable artifactregistry.googleapis.com  # For Artifact Registry (recommended)
   ```

## Quick Deployment

### Option 1: Using Artifact Registry (Recommended)

1. **Create Artifact Registry repository** (one-time setup):
   ```bash
   gcloud artifacts repositories create rag-pipeline-repo \
     --repository-format=docker \
     --location=us-central1 \
     --description="RAG Pipeline Docker repository"
   ```

2. **Authenticate Docker**:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   gcloud auth configure-docker us-central1-docker.pkg.dev
   ```

3. **Tag and push image**:
   ```bash
   # Replace YOUR_PROJECT_ID and REGION with your values
   PROJECT_ID="your-project-id"
   REGION="us-central1"
   IMAGE_NAME="rag-pipeline"
   REPOSITORY="rag-pipeline-repo"
   
   docker tag rag-pipeline-test:latest \
     ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest
   
   docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest
   ```

4. **Deploy to Cloud Run**:
   ```bash
   gcloud run deploy rag-pipeline \
     --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest \
     --platform managed \
     --region ${REGION} \
     --allow-unauthenticated \
     --port 8080 \
     --memory 2Gi \
     --cpu 2 \
     --timeout 300 \
     --max-instances 10
   ```

### Option 2: Using Container Registry (Legacy)

1. **Authenticate Docker**:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   gcloud auth configure-docker
   ```

2. **Tag and push image**:
   ```bash
   PROJECT_ID="your-project-id"
   docker tag rag-pipeline-test:latest gcr.io/${PROJECT_ID}/rag-pipeline:latest
   docker push gcr.io/${PROJECT_ID}/rag-pipeline:latest
   ```

3. **Deploy to Cloud Run**:
   ```bash
   gcloud run deploy rag-pipeline \
     --image gcr.io/${PROJECT_ID}/rag-pipeline:latest \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --port 8080 \
     --memory 2Gi \
     --cpu 2
   ```

## Using the Deployment Script

1. **Make the script executable**:
   ```bash
   chmod +x deploy-to-cloud-run.sh
   ```

2. **Run the script**:
   ```bash
   ./deploy-to-cloud-run.sh YOUR_PROJECT_ID us-central1 rag-pipeline
   ```

## Setting Environment Variables and Secrets

### Using Environment Variables (for non-sensitive data):
```bash
gcloud run services update rag-pipeline \
  --region us-central1 \
  --update-env-vars \
    PINECONE_CLOUD=aws,\
    PINECONE_REGION=us-east-1,\
    OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

### Using Secrets (Recommended for API keys):

1. **Create secrets**:
   ```bash
   echo -n "your-openai-key" | gcloud secrets create openai-api-key --data-file=-
   echo -n "your-pinecone-key" | gcloud secrets create pinecone-api-key --data-file=-
   echo -n "your-jwt-secret" | gcloud secrets create jwt-secret-key --data-file=-
   ```

2. **Grant Cloud Run access to secrets**:
   ```bash
   PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)")
   gcloud secrets add-iam-policy-binding openai-api-key \
     --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   
   gcloud secrets add-iam-policy-binding pinecone-api-key \
     --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   
   gcloud secrets add-iam-policy-binding jwt-secret-key \
     --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

3. **Deploy with secrets**:
   ```bash
   gcloud run deploy rag-pipeline \
     --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest \
     --platform managed \
     --region ${REGION} \
     --set-secrets \
       OPENAI_API_KEY=openai-api-key:latest,\
       PINECONE_API_KEY=pinecone-api-key:latest,\
       JWT_SECRET_KEY=jwt-secret-key:latest
   ```

## Manual Steps via Google Cloud Console

1. **Push Image**:
   - Build and tag your image locally
   - Push to Container Registry or Artifact Registry using the commands above

2. **Deploy to Cloud Run**:
   - Go to Cloud Run in Google Cloud Console
   - Click "Create Service"
   - Select "Deploy one revision from an existing container image"
   - Enter your image URL (e.g., `us-central1-docker.pkg.dev/PROJECT_ID/repo/image:latest`)
   - Configure service settings:
     - **Container port**: 8080
     - **Memory**: 2Gi (or more)
     - **CPU**: 2 (or more)
     - **Timeout**: 300 seconds
     - **Max instances**: 10 (adjust as needed)
   - Add environment variables or secrets
   - Click "Create"

## Updating the Deployment

After making code changes:

1. **Rebuild and push new image**:
   ```bash
   docker build -t rag-pipeline-test .
   docker tag rag-pipeline-test:latest \
     ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest
   docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest
   ```

2. **Deploy new revision**:
   ```bash
   gcloud run deploy rag-pipeline \
     --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest \
     --region ${REGION}
   ```

## Useful Commands

- **View service details**: `gcloud run services describe rag-pipeline --region us-central1`
- **View logs**: `gcloud run services logs read rag-pipeline --region us-central1`
- **List revisions**: `gcloud run revisions list --service rag-pipeline --region us-central1`
- **Get service URL**: `gcloud run services describe rag-pipeline --region us-central1 --format="value(status.url)"`

## Troubleshooting

- **Permission denied**: Make sure you're authenticated and have the necessary IAM roles
- **Image not found**: Verify the image was pushed successfully and the path is correct
- **Container crashes**: Check logs and ensure environment variables/secrets are set correctly
- **Port issues**: Ensure your app listens on the PORT environment variable (Cloud Run sets this)

