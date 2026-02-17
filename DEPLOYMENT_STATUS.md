# Cloud Run Deployment Status

## ✅ Completed

### 1. Code Updates
- **scraper.py**: Added Flask HTTP server with `/` and `/health` endpoints
- **requirements.txt**: Added Flask 3.0.0 dependency
- **GitHub**: Code pushed to https://github.com/ed-at-kave/prenfe_scraper (main branch)
- **Documentation**: Updated CLOUD_RUN_DEPLOYMENT.md with HTTP server requirements

### 2. Docker Image
- **Built**: Docker image with Flask HTTP server support
- **Image**: `europe-west1-docker.pkg.dev/kave-home-dwh-ds/prenfe/prenfe-scraper:latest`
- **Digest**: `sha256:ca112a7dbb84acd2a6bc829435546f3d6971c31bfd420554896c47e6542adad5`
- **Pushed**: Successfully to Artifact Registry

### 3. Cloud Run Service
- **Status**: ✅ Running and healthy
- **Service Name**: prenfe-scraper
- **Region**: europe-west1
- **URL**: https://prenfe-scraper-498526804762.europe-west1.run.app
- **Configuration**:
  - Memory: 512Mi
  - CPU: 1
  - Timeout: 3600s (1 hour)
  - Max instances: 1
  - Authentication: Required (no-allow-unauthenticated)
  - Environment variables: GCS_BUCKET_NAME, GCS_FOLDER_NAME
- **Endpoints**:
  - `POST /`: Trigger fetch cycle (returns `{"status":"success","message":"Fetch cycle completed"}`)
  - `GET /health`: Health check (returns `{"status":"ok"}`)

### 4. Service Account
- **Name**: prenfe-scraper@kave-home-dwh-ds.iam.gserviceaccount.com
- **Permissions**:
  - roles/storage.objectCreator
  - roles/storage.objectViewer
  - roles/logging.logWriter

## ⏳ Pending (Manual Steps)

### Cloud Scheduler Jobs
The Cloud Scheduler jobs need to be created to trigger the Cloud Run service at scheduled intervals. Use one of these approaches:

#### Option A: Using gcloud (manual)

```bash
SERVICE_URL="https://prenfe-scraper-498526804762.europe-west1.run.app"
PROJECT_ID="kave-home-dwh-ds"
REGION="europe-west1"
ACCOUNT="prenfe-scraper@${PROJECT_ID}.iam.gserviceaccount.com"

# Peak morning (05:30-09:30) - every 1 minute
gcloud scheduler jobs create http prenfe-peak-morning \
  --location=$REGION \
  --schedule="*/1 5-8 * * *" \
  --uri="${SERVICE_URL}/" \
  --http-method=POST \
  --oidc-service-account-email=$ACCOUNT \
  --oidc-token-audience="$SERVICE_URL/" \
  --project=$PROJECT_ID

# Off-peak day (09:30-16:00) - every 10 minutes
gcloud scheduler jobs create http prenfe-offpeak-day \
  --location=$REGION \
  --schedule="*/10 9-15 * * *" \
  --uri="${SERVICE_URL}/" \
  --http-method=POST \
  --oidc-service-account-email=$ACCOUNT \
  --oidc-token-audience="$SERVICE_URL/" \
  --project=$PROJECT_ID

# Peak evening (16:00-18:30) - every 1 minute
gcloud scheduler jobs create http prenfe-peak-evening \
  --location=$REGION \
  --schedule="*/1 16-18 * * *" \
  --uri="${SERVICE_URL}/" \
  --http-method=POST \
  --oidc-service-account-email=$ACCOUNT \
  --oidc-token-audience="$SERVICE_URL/" \
  --project=$PROJECT_ID

# Off-peak evening (18:30-23:59) - every 10 minutes
gcloud scheduler jobs create http prenfe-offpeak-evening \
  --location=$REGION \
  --schedule="*/10 18-23 * * *" \
  --uri="${SERVICE_URL}/" \
  --http-method=POST \
  --oidc-service-account-email=$ACCOUNT \
  --oidc-token-audience="$SERVICE_URL/" \
  --project=$PROJECT_ID
```

#### Option B: Using Terraform

Install Terraform and run:
```bash
terraform init
terraform plan
terraform apply
```

See `cloud_run_main.tf` for infrastructure definition.

## Testing

### Manual Trigger Test
```bash
SERVICE_URL="https://prenfe-scraper-498526804762.europe-west1.run.app"
TOKEN=$(gcloud auth print-identity-token)

# Health check
curl -X GET "${SERVICE_URL}/health" \
  -H "Authorization: Bearer ${TOKEN}"

# Trigger fetch cycle
curl -X POST "${SERVICE_URL}/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### View Logs
```bash
gcloud run logs read prenfe-scraper \
  --region=europe-west1 \
  --project=kave-home-dwh-ds \
  --limit=50 \
  --follow
```

### Check Scheduled Jobs
Once created, view all scheduler jobs:
```bash
gcloud scheduler jobs list --location=europe-west1 --project=kave-home-dwh-ds
```

## Architecture

### How It Works
1. Cloud Scheduler triggers the Cloud Run service via HTTP POST at scheduled intervals
2. Cloud Run executes Flask endpoint `/` which calls `run_fetch_cycle()`
3. Scraper fetches data from RENFE API and processes two flows:
   - **general-prenfe**: All trains (saved locally and uploaded to GCS)
   - **prenfe-cat**: Regional trains only (filtered data, saved locally and uploaded to GCS)
4. Files uploaded to: `gs://beta-tests/prenfe-data/`
5. Logs written to Cloud Logging

### Scheduling
- **Peak Morning**: 05:30-09:30 → Every 1 minute
- **Off-peak Day**: 09:30-16:00 → Every 10 minutes
- **Peak Evening**: 16:00-18:30 → Every 1 minute
- **Off-peak Evening**: 18:30-00:00 → Every 10 minutes
- **Sleep**: 00:00-05:30 → No queries

## Data Flow
```
Cloud Scheduler (HTTP POST)
         ↓
Cloud Run Service (Port 8080)
         ↓
Flask Endpoint (/)
         ↓
run_fetch_cycle()
         ↓
┌─────────────────────┐
│  Fetch RENFE API    │
│ (flota.json endpoint)│
└─────────────────────┘
         ↓
    ┌────┴────┐
    ↓         ↓
[General] [Regional]
    ↓         ↓
  Local      Local
    ↓         ↓
  GCS        GCS
    ↓         ↓
 Logs       Logs
```

## Cost Estimation
- **Compute**: ~2,200 executions/day × 60 seconds = ~36,000 GB-seconds/month
  - Cost: ~$0.60/month (first 180,000 GB-seconds free)
- **Cloud Scheduler**: ~4,000 jobs/month
  - Cost: ~$0.20/month (first 3,650 jobs free)
- **Cloud Logging**: Minimal (~$0.10/month)
- **Cloud Storage**: Existing bucket charges
- **Total**: ~$0.90/month (mostly free tier)

## Next Steps
1. Create Cloud Scheduler jobs (using gcloud or Terraform)
2. Monitor logs in Cloud Logging
3. Verify data is being saved to GCS bucket
4. Set up alerts (optional) for failed jobs
5. Monitor Cloud Run metrics
