output "api_service_account_email" {
  description = "API Cloud Run runtime service account email."
  value       = google_service_account.api.email
}

output "web_service_account_email" {
  description = "Web Cloud Run runtime service account email."
  value       = google_service_account.web.email
}

output "deployer_service_account_email" {
  description = "GitHub Actions deployer service account email."
  value       = google_service_account.deployer.email
}

output "workload_identity_provider" {
  description = "Provider resource name for GitHub Actions authentication."
  value       = google_iam_workload_identity_pool_provider.github.name
}
