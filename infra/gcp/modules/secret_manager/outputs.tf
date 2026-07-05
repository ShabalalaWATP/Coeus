output "secret_ids" {
  description = "Created secret IDs."
  value       = keys(google_secret_manager_secret.secret)
}

output "secret_names" {
  description = "Secret resource names keyed by secret ID."
  value       = { for key, secret in google_secret_manager_secret.secret : key => secret.name }
}
