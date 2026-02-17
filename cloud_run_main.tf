terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Service Account for Cloud Run
resource "google_service_account" "prenfe_scraper" {
  account_id   = "prenfe-scraper"
  display_name = "RENFE Scraper Service Account"
  project      = var.project_id

  labels = {
    "project" = "prenfe"
    "dept"    = "general"
  }
}

# Cloud Storage permissions
resource "google_project_iam_member" "prenfe_storage_creator" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.prenfe_scraper.email}"
}

resource "google_project_iam_member" "prenfe_storage_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.prenfe_scraper.email}"
}

# Cloud Logging permissions
resource "google_project_iam_member" "prenfe_logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.prenfe_scraper.email}"
}

# Cloud Run Service
resource "google_cloud_run_service" "prenfe_scraper" {
  name     = "prenfe-scraper"
  location = var.region
  project  = var.project_id

  labels = {
    "project" = "prenfe"
    "dept"    = "general"
  }

  template {
    spec {
      service_account_name = google_service_account.prenfe_scraper.email

      containers {
        image = var.container_image

        env {
          name  = "GCS_BUCKET_NAME"
          value = "beta-tests"
        }

        env {
          name  = "GCS_FOLDER_NAME"
          value = "prenfe-data"
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }

      timeout_seconds       = 3600
      service_account_name  = google_service_account.prenfe_scraper.email
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale" = "1"
        "autoscaling.knative.dev/minScale" = "0"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [
    google_project_iam_member.prenfe_storage_creator,
    google_project_iam_member.prenfe_storage_viewer,
    google_project_iam_member.prenfe_logging_writer
  ]
}

# Cloud Scheduler Job - Peak Morning (05:30-09:30, every 1 minute)
resource "google_cloud_scheduler_job" "prenfe_peak_morning" {
  name             = "prenfe-peak-morning"
  description      = "Trigger RENFE scraper during peak morning hours"
  schedule         = "*/1 5-8 * * *"  # Every minute, 5:00-8:59 (covers 05:30-09:30)
  time_zone        = "Europe/Madrid"
  region           = var.region
  project          = var.project_id
  attempt_deadline = "320s"

  labels = {
    "project" = "prenfe"
    "dept"    = "general"
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_service.prenfe_scraper.status[0].url}/"

    headers = {
      "Content-Type" = "application/json"
    }

    oidc_token {
      service_account_email = google_service_account.prenfe_scraper.email
      audience              = google_cloud_run_service.prenfe_scraper.status[0].url
    }
  }
}

# Cloud Scheduler Job - Off-peak Day (09:30-16:00, every 10 minutes)
resource "google_cloud_scheduler_job" "prenfe_offpeak_day" {
  name             = "prenfe-offpeak-day"
  description      = "Trigger RENFE scraper during off-peak daytime hours"
  schedule         = "*/10 9-15 * * *"  # Every 10 minutes, 9:00-15:59
  time_zone        = "Europe/Madrid"
  region           = var.region
  project          = var.project_id
  attempt_deadline = "320s"

  labels = {
    "project" = "prenfe"
    "dept"    = "general"
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_service.prenfe_scraper.status[0].url}/"

    headers = {
      "Content-Type" = "application/json"
    }

    oidc_token {
      service_account_email = google_service_account.prenfe_scraper.email
      audience              = google_cloud_run_service.prenfe_scraper.status[0].url
    }
  }
}

# Cloud Scheduler Job - Peak Evening (16:00-18:30, every 1 minute)
resource "google_cloud_scheduler_job" "prenfe_peak_evening" {
  name             = "prenfe-peak-evening"
  description      = "Trigger RENFE scraper during peak evening hours"
  schedule         = "*/1 16-18 * * *"  # Every minute, 16:00-18:59
  time_zone        = "Europe/Madrid"
  region           = var.region
  project          = var.project_id
  attempt_deadline = "320s"

  labels = {
    "project" = "prenfe"
    "dept"    = "general"
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_service.prenfe_scraper.status[0].url}/"

    headers = {
      "Content-Type" = "application/json"
    }

    oidc_token {
      service_account_email = google_service_account.prenfe_scraper.email
      audience              = google_cloud_run_service.prenfe_scraper.status[0].url
    }
  }
}

# Cloud Scheduler Job - Off-peak Evening (18:30-23:59, every 10 minutes)
resource "google_cloud_scheduler_job" "prenfe_offpeak_evening" {
  name             = "prenfe-offpeak-evening"
  description      = "Trigger RENFE scraper during off-peak evening hours"
  schedule         = "*/10 18-23 * * *"  # Every 10 minutes, 18:00-23:59
  time_zone        = "Europe/Madrid"
  region           = var.region
  project          = var.project_id
  attempt_deadline = "320s"

  labels = {
    "project" = "prenfe"
    "dept"    = "general"
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_service.prenfe_scraper.status[0].url}/"

    headers = {
      "Content-Type" = "application/json"
    }

    oidc_token {
      service_account_email = google_service_account.prenfe_scraper.email
      audience              = google_cloud_run_service.prenfe_scraper.status[0].url
    }
  }
}

# Outputs
output "cloud_run_service_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_service.prenfe_scraper.status[0].url
}

output "service_account_email" {
  description = "Service account email"
  value       = google_service_account.prenfe_scraper.email
}

output "scheduler_jobs" {
  description = "Cloud Scheduler job names"
  value = {
    peak_morning   = google_cloud_scheduler_job.prenfe_peak_morning.name
    offpeak_day    = google_cloud_scheduler_job.prenfe_offpeak_day.name
    peak_evening   = google_cloud_scheduler_job.prenfe_peak_evening.name
    offpeak_evening = google_cloud_scheduler_job.prenfe_offpeak_evening.name
  }
}
