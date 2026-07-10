mock_provider "google" {}

variables {
  project_id        = "synthetic-project"
  project_number    = "123456789012"
  github_repository = "synthetic/coeus"
  api_image         = "europe-west2-docker.pkg.dev/synthetic-project/coeus/api:test"
  web_image         = "europe-west2-docker.pkg.dev/synthetic-project/coeus/web:test"
}

run "gcp_apply_is_blocked_until_migration_adapters_are_ready" {
  command = plan

  expect_failures = [terraform_data.migration_readiness_gate]
}
