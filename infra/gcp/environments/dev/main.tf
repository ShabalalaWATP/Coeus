locals {
  name_prefix = "coeus-${var.environment}"
  labels = {
    app         = "coeus"
    environment = var.environment
    managed_by  = "terraform"
  }

  required_services = toset([
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudkms.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
    "pubsub.googleapis.com",
  ])

  secret_ids = toset([
    "${local.name_prefix}-database-url",
    "${local.name_prefix}-session-secret",
    "${local.name_prefix}-csrf-secret",
    "${local.name_prefix}-local-seed-credential",
    "${local.name_prefix}-llm-provider-config",
    "${local.name_prefix}-object-storage-config",
  ])

  bucket_names = toset([
    "${local.name_prefix}-product-assets",
    "${local.name_prefix}-generated-previews",
    "${local.name_prefix}-audit-exports",
    "${local.name_prefix}-storage-access-logs",
  ])

  topic_names = toset([
    "${local.name_prefix}.ticket.created",
    "${local.name_prefix}.ticket.updated",
    "${local.name_prefix}.ticket.state_changed",
    "${local.name_prefix}.agent.run_requested",
    "${local.name_prefix}.agent.run_completed",
    "${local.name_prefix}.product.ingest_requested",
    "${local.name_prefix}.product.index_requested",
    "${local.name_prefix}.product.qc_approved",
    "${local.name_prefix}.product.disseminated",
    "${local.name_prefix}.feedback.received",
    "${local.name_prefix}.analytics.rebuild_requested",
  ])

  artifact_registry_service_agent = "service-${var.project_number}@gcp-sa-artifactregistry.iam.gserviceaccount.com"
  pubsub_service_agent            = "service-${var.project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "terraform_data" "migration_readiness_gate" {
  lifecycle {
    precondition {
      condition     = var.migration_adapters_ready
      error_message = "GCP apply is disabled until the GCS, Pub/Sub and distributed-state migration gates are implemented and verified."
    }
  }
}

module "project_services" {
  source = "../../modules/project_services"

  project_id = var.project_id
  services   = local.required_services
}

module "iam" {
  source = "../../modules/iam"

  project_id        = var.project_id
  github_repository = var.github_repository
  environment       = var.environment

  depends_on = [module.project_services]
}

module "artifact_registry" {
  source = "../../modules/artifact_registry"

  repository_id = "coeus"
  region        = var.region
  labels        = local.labels
  kms_key_name  = module.kms.crypto_key_id

  depends_on = [module.kms]
}

module "kms" {
  source = "../../modules/kms"

  key_ring_name   = "${local.name_prefix}-security"
  crypto_key_name = "${local.name_prefix}-application"
  region          = var.region
  labels          = local.labels
  crypto_key_users = toset([
    "serviceAccount:${local.artifact_registry_service_agent}",
    "serviceAccount:${local.pubsub_service_agent}",
  ])

  depends_on = [module.project_services]
}

module "secrets" {
  source = "../../modules/secret_manager"

  secret_ids = local.secret_ids
  labels     = local.labels

  depends_on = [module.project_services]
}

module "storage" {
  source = "../../modules/cloud_storage"

  buckets                = local.bucket_names
  region                 = var.region
  labels                 = local.labels
  access_log_bucket_name = "${local.name_prefix}-storage-access-logs"

  depends_on = [module.project_services]
}

module "pubsub" {
  source = "../../modules/pubsub"

  project_id     = var.project_id
  project_number = var.project_number
  topic_names    = local.topic_names
  labels         = local.labels
  kms_key_name   = module.kms.crypto_key_id

  depends_on = [module.kms]
}

module "database" {
  source = "../../modules/cloud_sql_postgres"

  instance_name       = "${local.name_prefix}-postgres"
  region              = var.region
  database_name       = "coeus"
  deletion_protection = var.cloud_sql_deletion_protection
  labels              = local.labels

  depends_on = [module.project_services]
}

resource "google_project_iam_member" "api_cloud_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${module.iam.api_service_account_email}"
}

resource "google_secret_manager_secret_iam_member" "api_secret_access" {
  for_each = local.secret_ids

  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${module.iam.api_service_account_email}"

  depends_on = [module.secrets]
}

resource "google_storage_bucket_iam_member" "api_bucket_access" {
  for_each = local.bucket_names

  bucket = each.value
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.iam.api_service_account_email}"

  depends_on = [module.storage]
}

resource "google_pubsub_topic_iam_member" "api_topic_publisher" {
  for_each = local.topic_names

  project = var.project_id
  topic   = each.value
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${module.iam.api_service_account_email}"

  depends_on = [module.pubsub]
}

module "api" {
  source = "../../modules/cloud_run_service"

  name                  = "${local.name_prefix}-api"
  region                = var.region
  image                 = var.api_image
  service_account_email = module.iam.api_service_account_email
  container_port        = 8000
  max_instance_count    = 1
  single_writer         = true
  allow_unauthenticated = true
  cloud_sql_instances   = [module.database.connection_name]
  labels                = local.labels

  environment_variables = {
    COEUS_ENVIRONMENT                   = var.environment
    COEUS_ALLOWED_CORS_ORIGINS          = jsonencode(var.allowed_cors_origins)
    COEUS_GCP_PROJECT_ID                = var.project_id
    COEUS_GCP_REGION                    = var.region
    COEUS_SECURE_COOKIES                = "true"
    COEUS_ALLOW_DEV_SEED_USERS          = "true"
    COEUS_OBJECT_STORAGE_PROVIDER       = "gcs"
    COEUS_GCS_PRODUCT_ASSETS_BUCKET     = "${local.name_prefix}-product-assets"
    COEUS_GCS_GENERATED_PREVIEWS_BUCKET = "${local.name_prefix}-generated-previews"
    COEUS_PUBSUB_ENABLED                = "true"
    COEUS_PUBSUB_TOPIC_PREFIX           = local.name_prefix
    COEUS_LLM_PROVIDER                  = "mock"
    COEUS_EMBEDDING_PROVIDER            = "mock"
  }

  secret_environment_variables = {
    COEUS_DATABASE_URL          = "${local.name_prefix}-database-url"
    COEUS_SESSION_SECRET        = "${local.name_prefix}-session-secret"
    COEUS_CSRF_SECRET           = "${local.name_prefix}-csrf-secret"
    COEUS_LOCAL_SEED_CREDENTIAL = "${local.name_prefix}-local-seed-credential"
  }

  depends_on = [
    terraform_data.migration_readiness_gate,
    google_project_iam_member.api_cloud_sql_client,
    google_secret_manager_secret_iam_member.api_secret_access,
    google_storage_bucket_iam_member.api_bucket_access,
    google_pubsub_topic_iam_member.api_topic_publisher,
  ]
}

module "web" {
  source = "../../modules/cloud_run_service"

  name                  = "${local.name_prefix}-web"
  region                = var.region
  image                 = var.web_image
  service_account_email = module.iam.web_service_account_email
  container_port        = 8080
  max_instance_count    = 3
  single_writer         = false
  allow_unauthenticated = true
  labels                = local.labels

  environment_variables = {
    COEUS_ENVIRONMENT = var.environment
  }

  depends_on = [terraform_data.migration_readiness_gate]
}
