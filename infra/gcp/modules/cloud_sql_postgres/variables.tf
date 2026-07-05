variable "instance_name" {
  description = "Cloud SQL instance name."
  type        = string
}

variable "region" {
  description = "Cloud SQL region."
  type        = string
}

variable "database_name" {
  description = "Application database name."
  type        = string
}

variable "tier" {
  description = "Cloud SQL machine tier."
  type        = string
  default     = "db-f1-micro"
}

variable "deletion_protection" {
  description = "Whether deletion protection is enabled."
  type        = bool
  default     = true
}

variable "labels" {
  description = "Labels applied to Cloud SQL resources."
  type        = map(string)
  default     = {}
}
