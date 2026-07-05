locals {
  github_repository_owner = split("/", var.github_repository)[0]
  deployer_roles = toset([
    "roles/artifactregistry.writer",
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
  #checkov:skip=CKV_GCP_125:Subject is branch-bound through the github_repository module variable.
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"
  attribute_condition                = "assertion.sub == 'repo:${var.github_repository}:ref:refs/heads/main' && assertion.repository == '${var.github_repository}' && assertion.repository_owner == '${local.github_repository_owner}'"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.ref"              = "assertion.ref"
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

resource "google_service_account_iam_member" "deployer_api_service_account_user" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.deployer.member
}

resource "google_service_account_iam_member" "deployer_web_service_account_user" {
  service_account_id = google_service_account.web.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.deployer.member
}
