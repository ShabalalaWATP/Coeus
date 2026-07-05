variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "services" {
  description = "Service APIs that must be enabled for the environment."
  type        = set(string)
}
