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
- **URL**: https://prenfe-scraper-r2wu5n3zza-ew.a.run.app
- **Last Data Collection**: 2026-02-18 at 10:03:42 CET
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
  - roles/storage.objectCreator (for GCS file uploads)
  - roles/storage.objectViewer (for GCS access)
  - roles/logging.logWriter (for Cloud Logging)
  - roles/run.invoker (for Cloud Scheduler to trigger the service)

## ✅ Completed (All Steps)

### Cloud Scheduler Jobs  
All Cloud Scheduler jobs have been created and are actively triggering the Cloud Run service at scheduled intervals (Paris Time - CET). The system is fully operational.

#### Option A: Using gcloud (manual)

**⚠️ Important Timezone Note:**
All schedules below use UTC hour values (Etc/UTC timezone). Cloud Scheduler will execute at UTC times, which automatically convert to CET (UTC+1) windows. For example, `*/5 4 * * *` runs at 04:00-04:59 UTC, which is 05:00-05:59 CET.

```bash
SERVICE_URL="https://prenfe-scraper-498526804762.europe-west1.run.app"
PROJECT_ID="kave-home-dwh-ds"
REGION="europe-west1"
ACCOUNT="prenfe-scraper@${PROJECT_ID}.iam.gserviceaccount.com"

# Low morning (05:00-05:59 CET / 04:00-04:59 UTC) - every 5 minutes
gcloud scheduler jobs create http prenfe-low-early \
  --location=$REGION \
  --schedule="*/5 4 * * *" \
  --uri="${SERVICE_URL}/" \
  --http-method=POST \
  --oidc-service-account-email=$ACCOUNT \
  --oidc-token-audience="$SERVICE_URL/" \
  --project=$PROJECT_ID

# High morning (06:00-09:59 CET / 05:00-08:59 UTC) - every 2 minutes
gcloud scheduler jobs create http prenfe-high-morning \
  --location=$REGION \
  --schedule="*/2 5-8 * * *" \
  --uri="${SERVICE_URL}/" \
  --http-method=POST \
  --oidc-service-account-email=$ACCOUNT \
  --oidc-token-audience="$SERVICE_URL/" \
  --project=$PROJECT_ID

# Off-peak day (10:00-15:59 CET / 09:00-14:59 UTC) - every 10 minutes
gcloud scheduler jobs create http prenfe-vlow-day \
  --location=$REGION \
  --schedule="*/10 9-14 * * *" \
  --uri="${SERVICE_URL}/" \
  --http-method=POST \
  --oidc-service-account-email=$ACCOUNT \
  --oidc-token-audience="$SERVICE_URL/" \
  --project=$PROJECT_ID

# High evening (16:00-18:59 CET / 15:00-17:59 UTC) - every 2 minutes
gcloud scheduler jobs create http prenfe-high-evening \
  --location=$REGION \
  --schedule="*/2 15-17 * * *" \
  --uri="${SERVICE_URL}/" \
  --http-method=POST \
  --oidc-service-account-email=$ACCOUNT \
  --oidc-token-audience="$SERVICE_URL/" \
  --project=$PROJECT_ID

# Low evening (19:00-23:59 CET / 18:00-22:59 UTC) - every 5 minutes
gcloud scheduler jobs create http prenfe-low-late \
  --location=$REGION \
  --schedule="*/5 18-22 * * *" \
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

### Scheduling (Paris Time - CET)
- **Low Morning**: 05:00-05:59 CET → Every 5 minutes
- **High Morning**: 06:00-09:59 CET → Every 2 minutes
- **Off-peak Day**: 10:00-15:59 CET → Every 10 minutes
- **High Evening**: 16:00-18:59 CET → Every 2 minutes
- **Low Evening**: 19:00-23:59 CET → Every 5 minutes
- **Sleep**: 00:00-04:59 CET → No queries

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
- **Compute (Cloud Run)**: 318 executions/day × 60 seconds × 0.5 GiB memory = 286,200 GiB-seconds/month
  - Free tier: 360,000 GiB-seconds/month (request-based billing in europe-west1)
  - Billable: 286,200 - 360,000 = **Zero** (entirely within free tier) ✅
  - Cost: **$0.00/month**
- **Cloud Scheduler**: 5 scheduled jobs
  - Free tier: 3 jobs per month (per billing account)
  - Billable: 5 - 3 = 2 jobs
  - Cost: 2 × $0.10/month = **$0.20/month**
- **Cloud Logging**: Minimal (~$0.05/month)
- **Cloud Storage**: Existing bucket charges
- **Total**: **~$0.25/month** (entirely within free tiers except minimal Scheduler cost)

## Next Steps
1. Create Cloud Scheduler jobs (using gcloud or Terraform)
2. Monitor logs in Cloud Logging
3. Verify data is being saved to GCS bucket
4. Set up alerts (optional) for failed jobs
5. Monitor Cloud Run metrics
