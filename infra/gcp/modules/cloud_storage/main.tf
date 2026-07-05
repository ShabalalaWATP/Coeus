resource "google_storage_bucket" "bucket" {
  for_each = var.buckets

  name                        = each.value
  location                    = var.region
  labels                      = var.labels
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  versioning {
    enabled = true
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
