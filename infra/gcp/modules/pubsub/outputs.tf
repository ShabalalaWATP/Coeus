output "topic_names" {
  description = "Created primary topic names."
  value       = keys(google_pubsub_topic.topic)
}

output "subscription_names" {
  description = "Created worker subscription names."
  value       = keys(google_pubsub_subscription.worker)
}
