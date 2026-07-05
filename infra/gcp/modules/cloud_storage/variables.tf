variable "buckets" {
  description = "Bucket IDs to create."
  type        = set(string)
}

variable "region" {
  description = "Bucket location."
  type        = string
}

variable "labels" {
  description = "Labels applied to buckets."
  type        = map(string)
  default     = {}
}
