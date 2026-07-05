variable "project_id" {
  description = "GCP project ID."
  type        = string
  default     = "coeus-501415"
}

variable "project_number" {
  description = "GCP project number."
  type        = string
  default     = "710037672478"
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
  default     = "ShabalalaWATP/Coeus"
}

variable "api_image" {
  description = "Initial API image. The deploy workflow replaces this by SHA."
  type        = string
  default     = "europe-west2-docker.pkg.dev/coeus-501415/coeus/coeus-api:bootstrap"
}

variable "web_image" {
  description = "Initial web image. The deploy workflow replaces this by SHA."
  type        = string
  default     = "europe-west2-docker.pkg.dev/coeus-501415/coeus/coeus-web:bootstrap"
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
