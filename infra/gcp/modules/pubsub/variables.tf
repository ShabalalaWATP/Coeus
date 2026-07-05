variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "project_number" {
  description = "GCP project number for the Pub/Sub service agent."
  type        = string
}

variable "topic_names" {
  description = "Topic names to create."
  type        = set(string)
}

variable "labels" {
  description = "Labels applied to topics and subscriptions."
  type        = map(string)
  default     = {}
}
