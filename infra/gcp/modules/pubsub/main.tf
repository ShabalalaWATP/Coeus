locals {
  pubsub_service_agent = "service-${var.project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_topic" "topic" {
  for_each = var.topic_names

  name         = each.value
  kms_key_name = var.kms_key_name
  labels       = var.labels
}

resource "google_pubsub_topic" "dead_letter" {
  for_each = var.topic_names

  name         = "${each.value}.dead-letter"
  kms_key_name = var.kms_key_name
  labels       = var.labels
}

resource "google_pubsub_subscription" "worker" {
  for_each = var.topic_names

  name                       = "${each.value}.worker"
  topic                      = google_pubsub_topic.topic[each.key].id
  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"
  labels                     = var.labels

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter[each.key].id
    max_delivery_attempts = 5
  }
}

resource "google_pubsub_topic_iam_member" "dead_letter_publisher" {
  for_each = var.topic_names

  project = var.project_id
  topic   = google_pubsub_topic.dead_letter[each.key].name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${local.pubsub_service_agent}"
}

resource "google_pubsub_subscription_iam_member" "dead_letter_subscriber" {
  for_each = var.topic_names

  project      = var.project_id
  subscription = google_pubsub_subscription.worker[each.key].name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${local.pubsub_service_agent}"
}
