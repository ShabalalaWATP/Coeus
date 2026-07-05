output "artifact_registry_repository_url" {
  description = "Docker repository URL for deployment images."
  value       = module.artifact_registry.repository_url
}

output "api_service_url" {
  description = "API Cloud Run URL."
  value       = module.api.uri
}

output "web_service_url" {
  description = "Web Cloud Run URL."
  value       = module.web.uri
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL instance connection name."
  value       = module.database.connection_name
}

output "deployer_service_account_email" {
  description = "Set this as GitHub variable GCP_DEPLOY_SERVICE_ACCOUNT."
  value       = module.iam.deployer_service_account_email
}

output "workload_identity_provider" {
  description = "Set this as GitHub variable GCP_WORKLOAD_IDENTITY_PROVIDER."
  value       = module.iam.workload_identity_provider
}
