variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for Cloud Run and Cloud Scheduler"
  type        = string
  default     = "europe-west1"
}

variable "container_image" {
  description = "Docker image URI for Cloud Run"
  type        = string
}
