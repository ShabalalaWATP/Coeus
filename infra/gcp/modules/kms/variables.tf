variable "key_ring_name" {
  description = "KMS key ring name."
  type        = string
}

variable "crypto_key_name" {
  description = "KMS crypto key name."
  type        = string
}

variable "region" {
  description = "KMS key ring location."
  type        = string
}

variable "crypto_key_users" {
  description = "IAM members allowed to encrypt and decrypt with the key."
  type        = set(string)
}

variable "labels" {
  description = "Labels applied to the crypto key."
  type        = map(string)
  default     = {}
}
