output "bucket_names" {
  description = "Created bucket names."
  value       = keys(google_storage_bucket.bucket)
}
