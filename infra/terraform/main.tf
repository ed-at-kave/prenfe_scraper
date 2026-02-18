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

# Cloud Scheduler Jobs - all use Europe/Paris timezone (CET/CEST, DST-aware)
# Cron expressions use local Paris time, Cloud Scheduler handles UTC conversion automatically.

# Low morning (05:00-05:59 Paris) - every 5 minutes
resource "google_cloud_scheduler_job" "prenfe_low_early" {
  name             = "prenfe-low-early"
  description      = "Trigger RENFE scraper during low morning hours (05:00-05:59 Paris)"
  schedule         = "*/5 5 * * *"
  time_zone        = "Europe/Paris"
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

# High morning (06:00-09:59 Paris) - every 2 minutes
resource "google_cloud_scheduler_job" "prenfe_high_morning" {
  name             = "prenfe-high-morning"
  description      = "Trigger RENFE scraper during high morning hours (06:00-09:59 Paris)"
  schedule         = "*/2 6-9 * * *"
  time_zone        = "Europe/Paris"
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

# Off-peak day (10:00-15:59 Paris) - every 10 minutes
resource "google_cloud_scheduler_job" "prenfe_vlow_day" {
  name             = "prenfe-vlow-day"
  description      = "Trigger RENFE scraper during off-peak daytime hours (10:00-15:59 Paris)"
  schedule         = "*/10 10-15 * * *"
  time_zone        = "Europe/Paris"
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

# High evening (16:00-18:59 Paris) - every 2 minutes
resource "google_cloud_scheduler_job" "prenfe_high_evening" {
  name             = "prenfe-high-evening"
  description      = "Trigger RENFE scraper during high evening hours (16:00-18:59 Paris)"
  schedule         = "*/2 16-18 * * *"
  time_zone        = "Europe/Paris"
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

# Low evening (19:00-23:59 Paris) - every 5 minutes
resource "google_cloud_scheduler_job" "prenfe_low_late" {
  name             = "prenfe-low-late"
  description      = "Trigger RENFE scraper during low evening hours (19:00-23:59 Paris)"
  schedule         = "*/5 19-23 * * *"
  time_zone        = "Europe/Paris"
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
    low_early     = google_cloud_scheduler_job.prenfe_low_early.name
    high_morning  = google_cloud_scheduler_job.prenfe_high_morning.name
    vlow_day      = google_cloud_scheduler_job.prenfe_vlow_day.name
    high_evening  = google_cloud_scheduler_job.prenfe_high_evening.name
    low_late      = google_cloud_scheduler_job.prenfe_low_late.name
  }
}
