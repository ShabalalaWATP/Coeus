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
