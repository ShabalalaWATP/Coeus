mock_provider "google" {}

variables {
  name                  = "coeus-test-api"
  region                = "europe-west2"
  image                 = "europe-west2-docker.pkg.dev/example/coeus/api:test"
  service_account_email = "coeus-api@example.iam.gserviceaccount.com"
  container_port        = 8000
}

run "single_writer_accepts_one_instance" {
  command = plan

  variables {
    single_writer      = true
    max_instance_count = 1
  }
}

run "single_writer_rejects_multiple_instances" {
  command = plan

  variables {
    single_writer      = true
    max_instance_count = 2
  }

  expect_failures = [google_cloud_run_v2_service.service]
}

run "stateless_service_can_scale" {
  command = plan

  variables {
    single_writer      = false
    max_instance_count = 3
  }
}
