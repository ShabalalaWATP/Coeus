locals {
  deployer_roles = toset([
    "roles/artifactregistry.writer",
    "roles/iam.serviceAccountUser",
    "roles/run.admin",
  ])
}

resource "google_service_account" "api" {
  account_id   = "coeus-${var.environment}-api"
  display_name = "Coeus ${var.environment} API runtime"
}

resource "google_service_account" "web" {
  account_id   = "coeus-${var.environment}-web"
  display_name = "Coeus ${var.environment} web runtime"
}

resource "google_service_account" "deployer" {
  account_id   = "coeus-${var.environment}-deployer"
  display_name = "Coeus ${var.environment} GitHub deployer"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "coeus-${var.environment}-github"
  display_name              = "Coeus ${var.environment} GitHub"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"
  attribute_condition                = "assertion.repository == '${var.github_repository}'"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_workload_identity" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

resource "google_project_iam_member" "deployer" {
  for_each = local.deployer_roles

  project = var.project_id
  role    = each.value
  member  = google_service_account.deployer.member
}
