output "crypto_key_id" {
  description = "KMS crypto key resource ID."
  value       = google_kms_crypto_key.coeus.id
}
