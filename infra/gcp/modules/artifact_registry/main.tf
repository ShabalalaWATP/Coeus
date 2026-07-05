resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = var.repository_id
  description   = "Coeus container images."
  format        = "DOCKER"
  kms_key_name  = var.kms_key_name
  labels        = var.labels
}
