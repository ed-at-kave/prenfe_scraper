# Cloud Run Deployment Guide

## Prerequisites

- GCP Project: `kave-home-dwh-ds`
- Artifact Registry enabled
- Cloud Run API enabled
- Cloud Scheduler API enabled
- Service account with appropriate permissions

## Step 1: Build and Push Docker Image

### 1.1 Set environment variables
```bash
PROJECT_ID="kave-home-dwh-ds"
REGION="europe-west1"
SERVICE_NAME="prenfe-scraper"
IMAGE_NAME="prenfe-scraper"
```

### 1.2 Configure Docker authentication
```bash
gcloud auth configure-docker europe-west1-docker.pkg.dev
```

### 1.3 Build Docker image
```bash
cd /home/eguiu/betas/Prenfe
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/prenfe/${IMAGE_NAME}:latest .
```

### 1.4 Push to Artifact Registry
```bash
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/prenfe/${IMAGE_NAME}:latest
```

## Step 2: Deploy to Cloud Run

### 2.1 Create service account for Cloud Run
```bash
gcloud iam service-accounts create prenfe-scraper \
  --display-name="RENFE Scraper Service Account" \
  --project=${PROJECT_ID}

# Get the service account email
SERVICE_ACCOUNT="prenfe-scraper@${PROJECT_ID}.iam.gserviceaccount.com"
```

### 2.2 Grant required permissions
```bash
# Cloud Storage write access
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/storage.objectCreator"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/storage.objectViewer"

# Cloud Logging write access
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/logging.logWriter"

# Cloud Run invoker (required for Cloud Scheduler to trigger the service)
gcloud run services add-iam-policy-binding ${SERVICE_NAME} \
  --region=${REGION} \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/run.invoker"
```

### 2.3 Deploy Cloud Run service
```bash
gcloud run deploy ${SERVICE_NAME} \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/prenfe/${IMAGE_NAME}:latest \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --service-account=${SERVICE_ACCOUNT} \
  --memory=512Mi \
  --cpu=1 \
  --timeout=3600 \
  --max-instances=1 \
  --no-allow-unauthenticated \
  --set-env-vars="GCS_BUCKET_NAME=beta-tests,GCS_FOLDER_NAME=prenfe-data"
```

## Step 3: Deploy with Terraform

Cloud Scheduler triggers the scraper at dynamic intervals using `Europe/Paris` timezone (DST-aware — works for both CET and CEST automatically):
- **Low morning (5-minute intervals)**: 05:00-05:59 Paris
- **High morning (2-minute intervals)**: 06:00-09:59 Paris
- **Off-peak (10-minute intervals)**: 10:00-15:59 Paris
- **High evening (2-minute intervals)**: 16:00-18:59 Paris
- **Low evening (5-minute intervals)**: 19:00-23:59 Paris
- **Sleep**: 00:00-04:59 Paris - no queries

### 3.1 HTTP Server Architecture

The scraper runs as a Flask HTTP server on port 8080:
- **POST /** - Cloud Scheduler triggers this endpoint to execute one fetch cycle
- **GET /health** - Health check endpoint for monitoring
- Each trigger executes one complete fetch cycle (general-prenfe + prenfe-cat flows)
- Cloud Scheduler handles all scheduling via cron expressions

### 3.2 Deploy Infrastructure with Terraform

```bash
# From the Prenfe project directory
cd /home/eguiu/betas/Prenfe

# Review the infrastructure plan
terraform plan

# Apply the infrastructure (creates Cloud Run service, service account, scheduler jobs)
terraform apply
```

This creates:
- **Cloud Run Service**: `prenfe-scraper` (512Mi memory, 1 CPU, 3600s timeout, max 1 instance)
- **Service Account**: `prenfe-scraper@kave-home-dwh-ds.iam.gserviceaccount.com`
- **IAM Roles**: Storage Object Creator/Viewer, Cloud Logging Writer
- **5 Cloud Scheduler Jobs** with HTTP POST triggers (`Europe/Paris` timezone — DST-aware):
  - `prenfe-low-early`: `*/5 5 * * *` (every 5 minutes, 05:00-05:59 Paris)
  - `prenfe-high-morning`: `*/2 6-9 * * *` (every 2 minutes, 06:00-09:59 Paris)
  - `prenfe-vlow-day`: `*/10 10-15 * * *` (every 10 minutes, 10:00-15:59 Paris)
  - `prenfe-high-evening`: `*/2 16-18 * * *` (every 2 minutes, 16:00-18:59 Paris)
  - `prenfe-low-late`: `*/5 19-23 * * *` (every 5 minutes, 19:00-23:59 Paris)

**Timezone**: All jobs use `Europe/Paris` IANA timezone. Cloud Scheduler automatically adjusts UTC execution times when DST changes (CET↔CEST), so no manual cron updates are needed twice a year.

Total daily executions: **318 calls/day** across all scheduling windows.

### 3.3 Flask HTTP Server (Already Configured)

The scraper.py file already includes the Flask HTTP server:
- Listens on `PORT` environment variable (default: 8080)
- **POST /** endpoint - Triggers one fetch cycle
- **GET /health** endpoint - Health check
- No code modifications needed before deployment

Flask is already in requirements.txt (v3.0.0+)

### 3.4 Verify IAM Permissions

After Terraform deployment, verify the service account has invoker role:

```bash
gcloud run services get-iam-policy prenfe-scraper \
  --region=europe-west1 \
  --project=kave-home-dwh-ds
```

The `prenfe-scraper` service account should have `roles/run.invoker` role.

## Step 4: Monitoring & Logs

## Monitoring and Logs

### View logs
```bash
gcloud run logs read ${SERVICE_NAME} \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --limit=50 \
  --follow
```

### Check Cloud Run service status
```bash
gcloud run services describe ${SERVICE_NAME} \
  --region=${REGION} \
  --project=${PROJECT_ID}
```

### Monitor with Cloud Logging
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}" \
  --limit=50 \
  --project=${PROJECT_ID}
```

## Estimated Costs

Based on the 318 daily executions across 5 scheduled jobs:

- **Compute (Cloud Run)**: 318 executions/day × 60 seconds × 0.5 GiB memory = 286,200 GiB-seconds/month
  - Free tier: 360,000 GiB-seconds/month (request-based billing in europe-west1)
  - Billable: 0 (entirely within free tier) ✅
  - Cost: **$0.00/month**
- **Cloud Scheduler**: 5 scheduled jobs
  - Free tier: 3 jobs per billing account per month
  - Billable: 2 jobs × $0.10/month
  - Cost: **$0.20/month**
- **Cloud Logging**: Minimal
  - Cost: **~$0.05/month**
- **Cloud Storage**: Already configured in GCS bucket
- **Total**: **~$0.25/month** (almost entirely free tier)

## Troubleshooting

### Service won't start
```bash
gcloud run logs read ${SERVICE_NAME} --region=${REGION} --limit=20
```

### Check service account permissions
```bash
gcloud projects get-iam-policy ${PROJECT_ID} \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:${SERVICE_ACCOUNT}"
```

### Test Cloud Run service locally
```bash
docker run -it --rm \
  -e GCS_BUCKET_NAME=beta-tests \
  -e GCS_FOLDER_NAME=prenfe-data \
  ${REGION}-docker.pkg.dev/${PROJECT_ID}/prenfe/${IMAGE_NAME}:latest
```

## Rollback

To rollback to a previous image version:
```bash
gcloud run deploy ${SERVICE_NAME} \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/prenfe/${IMAGE_NAME}:previous-version \
  --region=${REGION} \
  --project=${PROJECT_ID}
```

## Next Steps

1. Build and push Docker image
2. Deploy to Cloud Run
3. Set up Cloud Scheduler jobs
4. Monitor logs and validate data in GCS bucket
5. (Optional) Set up Cloud Monitoring alerts
