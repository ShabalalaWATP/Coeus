variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "project_number" {
  description = "GCP project number."
  type        = string
}

variable "region" {
  description = "Primary GCP region."
  type        = string
  default     = "europe-west2"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"
}

variable "github_repository" {
  description = "GitHub repository allowed to use workload identity."
  type        = string
}

variable "api_image" {
  description = "Initial API image. The deploy workflow replaces this by SHA."
  type        = string
}

variable "web_image" {
  description = "Initial web image. The deploy workflow replaces this by SHA."
  type        = string
}

variable "allowed_cors_origins" {
  description = "CORS origins allowed by the API."
  type        = list(string)
  default     = []
}

variable "cloud_sql_deletion_protection" {
  description = "Enable Cloud SQL deletion protection."
  type        = bool
  default     = false
}
