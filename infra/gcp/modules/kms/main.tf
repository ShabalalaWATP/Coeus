resource "google_kms_key_ring" "coeus" {
  name     = var.key_ring_name
  location = var.region
}

resource "google_kms_crypto_key" "coeus" {
  name            = var.crypto_key_name
  key_ring        = google_kms_key_ring.coeus.id
  rotation_period = "7776000s"
  labels          = var.labels

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key_iam_member" "crypto_key_user" {
  for_each = var.crypto_key_users

  crypto_key_id = google_kms_crypto_key.coeus.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = each.value
}
