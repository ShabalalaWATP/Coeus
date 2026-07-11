variable "name" {
  description = "Cloud Run service name."
  type        = string
}

variable "region" {
  description = "Cloud Run region."
  type        = string
}

variable "image" {
  description = "Container image to deploy."
  type        = string
}

variable "service_account_email" {
  description = "Runtime service account email."
  type        = string
}

variable "container_port" {
  description = "Container port."
  type        = number
}

variable "min_instance_count" {
  description = "Minimum Cloud Run instance count."
  type        = number
  default     = 0
}

variable "max_instance_count" {
  description = "Maximum Cloud Run instance count."
  type        = number
  default     = 1

  validation {
    condition     = var.max_instance_count >= 1
    error_message = "max_instance_count must be at least one."
  }
}

variable "single_writer" {
  description = "Require exactly one writable service instance."
  type        = bool
  default     = false
}

variable "environment_variables" {
  description = "Plain environment variables."
  type        = map(string)
  default     = {}
}

variable "secret_environment_variables" {
  description = "Environment variable names mapped to Secret Manager secret IDs."
  type        = map(string)
  default     = {}
}

variable "cloud_sql_instances" {
  description = "Cloud SQL instance connection names mounted into /cloudsql."
  type        = list(string)
  default     = []
}

variable "allow_unauthenticated" {
  description = "Whether allUsers can invoke the service."
  type        = bool
  default     = false
}

variable "ingress" {
  description = "Cloud Run ingress policy."
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "labels" {
  description = "Labels applied to the service."
  type        = map(string)
  default     = {}
}
