# RENFE Real-time Train Scraper

**Real-time train fleet data from Spanish National Railway Company (RENFE) → Google Cloud Storage**

A production-grade scraper that fetches live train fleet data from [RENFE](https://www.renfe.com) and saves it to Google Cloud Storage with intelligent scheduling based on demand patterns.

---

## Quick Start

### Local Development (1-2 minutes)

```bash
# 1. Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Run the scraper
python3 scraper.py

# Scrapes every 60 seconds. Press Ctrl+C to stop.
```

### With Docker

```bash
docker build -t prenfe-scraper .
docker run --rm -v $(pwd)/data:/app/data prenfe-scraper
```

---

## Architecture

```
Cloud Scheduler (Paris Time, CET)
        ↓
   HTTP POST triggers
        ↓
   Cloud Run Service
        ↓
RENFE API (flota.json)
        ↓
   Data Processing
   ├─ general-prenfe (all trains)
   └─ prenfe-cat (RG1/R11 regional trains)
        ↓
   Google Cloud Storage
```

### Schedule (Paris Time - CET)

| Time Window | Interval | Purpose |
|-------------|----------|---------|
| **05:00–05:59** | Every 5 min | Low morning traffic |
| **06:00–09:59** | Every 2 min | High morning demand |
| **10:00–15:59** | Every 10 min | Off-peak midday |
| **16:00–18:59** | Every 2 min | High evening demand |
| **19:00–23:59** | Every 5 min | Low evening traffic |
| **00:00–04:59** | OFF | Overnight sleep |

---

## Project Structure

```
prenfe/
├── README.md                    ← You are here
├── scraper.py                   ← Main entry point
├── requirements.txt             ← Python dependencies
├── Dockerfile                   ← Container build
│
├── tests/
│   └── test_scraper.py         ← Test suite
│
├── infra/
│   ├── terraform/              ← GCP infrastructure-as-code
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── terraform.tfvars
│   └── systemd/                ← Linux systemd setup (for on-prem servers)
│       ├── SETUP.md
│       └── prenfe-scraper.service
│
└── docs/
    ├── cloud-run-deployment.md ← Detailed Cloud Run guide
    └── deployment-status.md    ← Current deployment info
```

---

## Data Flows

### 1. **general-prenfe** (All Trains)
- Saves all train fleet data
- Output: `data/general-prenfe_YYYYMMDD_HHMMSS.json`
- Use case: Complete train network analysis

### 2. **prenfe-cat** (Catalan Regional Trains)
- Filters for RG1 and R11 regional trains (Catalonia focus)
- Output: `data/prenfe-cat_YYYYMMDD_HHMMSS.json`
- Use case: Regional rail monitoring

---

## Features

- ✅ **Real-time fetching** - Updates every 2-10 minutes (Paris Time schedule)
- ✅ **Two data flows** - General fleet + Catalan regional trains
- ✅ **Cloud-native** - Deploys to Cloud Run with Cloud Scheduler
- ✅ **Local fallback** - Runs standalone on-prem servers with systemd
- ✅ **GCS integration** - Automatic uploads to Google Cloud Storage
- ✅ **Comprehensive logging** - Separate logs for each data flow
- ✅ **Error handling** - Retries with exponential backoff
- ✅ **Connection pooling** - Efficient HTTP session management

---

## Local Testing

### Run All Tests

```bash
python3 -m pytest tests/ -v
```

### Run Specific Test

```bash
python3 -m pytest tests/test_scraper.py::TestScheduling -v
```

### Test Coverage

```bash
python3 -m pytest tests/ --cov=scraper --cov-report=html
```

---

## API Endpoint

**Base URL**: https://tiempo-real.renfe.com
**Endpoint**: `/renfe-visor/flota.json`
**Method**: GET
**Response**: JSON array with train fleet data

---

## Deployment

### Cloud Run (Recommended)

See [docs/cloud-run-deployment.md](docs/cloud-run-deployment.md) for:
- Docker build & push to Artifact Registry
- Cloud Run service configuration
- Cloud Scheduler job setup
- IAM permissions & service accounts

**Quick deploy**:
```bash
cd infra/terraform
terraform plan
terraform apply
```

### On-Premises (systemd)

See [infra/systemd/SETUP.md](infra/systemd/SETUP.md) for:
- Service installation
- Auto-start configuration
- Log viewing with journalctl
- Troubleshooting

**Quick install**:
```bash
sudo cp infra/systemd/prenfe-scraper.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable prenfe-scraper.service
sudo systemctl start prenfe-scraper.service
```

---

## Configuration

**Environment Variables**:
- `GCS_BUCKET_NAME` - GCS bucket for data storage (default: `beta-tests`)
- `GCS_FOLDER_NAME` - Subfolder within bucket (default: `prenfe-data`)

**Cloud Storage**:
- Enabled by default (`GCS_ENABLED = True` in scraper.py)
- Falls back to local `data/` directory if Cloud Storage unavailable
- Uses Application Default Credentials for authentication

---

## Monitoring

### Local Logs
```bash
tail -f logs/general-prenfe.log
tail -f logs/prenfe-cat.log
```

### Cloud Run Logs
```bash
gcloud run logs read prenfe-scraper --region europe-west1 --follow
```

### Check Deployment Status
See [docs/deployment-status.md](docs/deployment-status.md) for current Cloud Run service details.

---

## Troubleshooting

### Tests Failing?
```bash
# Verify environment
python3 -c "import requests; from google.cloud import storage; print('OK')"

# Run tests with output
python3 -m pytest tests/ -v -s
```

### Cloud Storage Not Working?
```bash
# Check authentication
gcloud auth list

# Verify bucket access
gsutil ls gs://beta-tests/prenfe-data/
```

### Service Won't Start?
```bash
# Check logs
sudo journalctl -u prenfe-scraper.service -n 50

# Verify service file
sudo systemd-analyze verify /etc/systemd/system/prenfe-scraper.service
```

---

## Development

### Add New Feature?
1. Write tests first (TDD)
2. Run existing tests to ensure no regression
3. Update README if behavior changes
4. Commit with clear message

### Update Schedule?
- For Cloud Run: Edit cron expressions in `infra/terraform/main.tf`
- For on-prem: Update `get_interval_for_time()` in `scraper.py`
- Always use **Paris Time (CET)** in schedule comments

---

## Stack

| Component | Technology |
|-----------|-----------|
| **Language** | Python 3.12+ |
| **HTTP** | requests (with connection pooling) |
| **Storage** | Google Cloud Storage |
| **Scheduler** | Cloud Scheduler (cron) |
| **Container** | Docker → Cloud Run |
| **IaC** | Terraform |
| **Testing** | pytest |
| **Logging** | Python logging + Cloud Logging |

---

## GCP Resources

**Project**: `kave-home-dwh-ds`
**Region**: `europe-west1` (Europe)
**Service Account**: `prenfe-scraper@kave-home-dwh-ds.iam.gserviceaccount.com`

---

## Cost Estimate

- **Compute (Cloud Run)**: 318 executions/day × 60 seconds × 0.5 GiB memory = 286,200 GiB-seconds/month
  - Free tier: 360,000 GiB-seconds/month (entirely within free tier) ✅
  - Cost: **$0.00/month**
- **Cloud Scheduler**: 5 jobs (2 billable after 3-job free tier)
  - Cost: **$0.20/month**
- **Cloud Logging**: Minimal
  - Cost: **~$0.05/month**
- **Cloud Storage**: Covered by existing GCS bucket
- **Total**: **~$0.25/month** (almost entirely free tier)

---

## License & Attribution

Data sourced from [RENFE](https://www.renfe.com) public API.

---

## Questions?

- **Cloud Run setup**: See [docs/cloud-run-deployment.md](docs/cloud-run-deployment.md)
- **Current deployment**: See [docs/deployment-status.md](docs/deployment-status.md)
- **Systemd setup**: See [infra/systemd/SETUP.md](infra/systemd/SETUP.md)
