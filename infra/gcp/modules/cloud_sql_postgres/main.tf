resource "google_sql_database_instance" "postgres" {
  #checkov:skip=CKV_GCP_79:PostgreSQL 16 is the pinned Cloud SQL baseline for dev compatibility.
  name                = var.instance_name
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.deletion_protection

  settings {
    tier              = var.tier
    availability_type = "ZONAL"
    disk_autoresize   = true
    disk_size         = 20
    disk_type         = "PD_SSD"
    user_labels       = var.labels

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "02:00"
    }

    database_flags {
      name  = "cloudsql.enable_pgaudit"
      value = "on"
    }

    database_flags {
      name  = "log_checkpoints"
      value = "on"
    }

    database_flags {
      name  = "log_connections"
      value = "on"
    }

    database_flags {
      name  = "log_disconnections"
      value = "on"
    }

    database_flags {
      name  = "log_duration"
      value = "on"
    }

    database_flags {
      name  = "log_hostname"
      value = "on"
    }

    database_flags {
      name  = "log_lock_waits"
      value = "on"
    }

    database_flags {
      name  = "log_min_error_statement"
      value = "error"
    }

    database_flags {
      name  = "log_statement"
      value = "ddl"
    }

    ip_configuration {
      ipv4_enabled = false
      ssl_mode     = "TRUSTED_CLIENT_CERTIFICATE_REQUIRED"
    }
  }
}

resource "google_sql_database" "app" {
  name     = var.database_name
  instance = google_sql_database_instance.postgres.name
}
