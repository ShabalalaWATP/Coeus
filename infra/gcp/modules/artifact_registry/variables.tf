variable "repository_id" {
  description = "Artifact Registry Docker repository ID."
  type        = string
}

variable "region" {
  description = "Artifact Registry region."
  type        = string
}

variable "labels" {
  description = "Labels applied to the repository."
  type        = map(string)
  default     = {}
}

variable "kms_key_name" {
  description = "Customer-managed KMS key used to encrypt repository contents."
  type        = string
  default     = null
}
