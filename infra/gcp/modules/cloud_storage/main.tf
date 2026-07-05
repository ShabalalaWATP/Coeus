# The logging block is dynamic because the access-log bucket is created by the same module.
resource "google_storage_bucket" "bucket" { # nosemgrep
  for_each = var.buckets

  name                        = each.value
  location                    = var.region
  labels                      = var.labels
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  dynamic "logging" {
    for_each = each.value == var.access_log_bucket_name ? [] : [var.access_log_bucket_name]
    content {
      log_bucket = logging.value
    }
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}
