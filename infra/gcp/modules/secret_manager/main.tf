resource "google_secret_manager_secret" "secret" {
  for_each = var.secret_ids

  secret_id = each.value
  labels    = var.labels

  replication {
    auto {}
  }
}
