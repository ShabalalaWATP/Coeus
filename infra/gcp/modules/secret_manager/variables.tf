variable "secret_ids" {
  description = "Secret IDs to create without storing secret values in Terraform."
  type        = set(string)
}

variable "labels" {
  description = "Labels applied to secrets."
  type        = map(string)
  default     = {}
}
