output "name" {
  description = "Cloud Run service name."
  value       = google_cloud_run_v2_service.service.name
}

output "uri" {
  description = "Cloud Run service URI."
  value       = google_cloud_run_v2_service.service.uri
}
