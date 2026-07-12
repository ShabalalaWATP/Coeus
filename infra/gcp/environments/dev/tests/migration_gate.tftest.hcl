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

run "targeted_project_services_plan_is_also_blocked" {
  command = plan

  plan_options {
    target = [module.project_services]
  }

  expect_failures = [terraform_data.migration_readiness_gate]
}

run "targeted_iam_plan_is_also_blocked" {
  command = plan

  plan_options {
    target = [module.iam]
  }

  expect_failures = [terraform_data.migration_readiness_gate]
}

run "targeted_kms_plan_is_also_blocked" {
  command = plan

  plan_options {
    target = [module.kms]
  }

  expect_failures = [terraform_data.migration_readiness_gate]
}

run "targeted_registry_plan_is_also_blocked" {
  command = plan

  plan_options {
    target = [module.artifact_registry]
  }

  expect_failures = [terraform_data.migration_readiness_gate]
}

run "targeted_secrets_plan_is_also_blocked" {
  command = plan

  plan_options {
    target = [module.secrets]
  }

  expect_failures = [terraform_data.migration_readiness_gate]
}

run "targeted_storage_plan_is_also_blocked" {
  command = plan

  plan_options {
    target = [module.storage]
  }

  expect_failures = [terraform_data.migration_readiness_gate]
}

run "targeted_pubsub_plan_is_also_blocked" {
  command = plan

  plan_options {
    target = [module.pubsub]
  }

  expect_failures = [terraform_data.migration_readiness_gate]
}

run "targeted_database_plan_is_also_blocked" {
  command = plan

  plan_options {
    target = [module.database]
  }

  expect_failures = [terraform_data.migration_readiness_gate]
}

run "targeted_api_plan_is_also_blocked" {
  command = plan

  plan_options {
    target = [module.api]
  }

  expect_failures = [terraform_data.migration_readiness_gate]
}

run "targeted_web_plan_is_also_blocked" {
  command = plan

  plan_options {
    target = [module.web]
  }

  expect_failures = [terraform_data.migration_readiness_gate]
}
