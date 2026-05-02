terraform {
  required_version = ">= 1.7.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.30"
    }
  }
  # Remote state in GCS.
  # Initialise with:
  #   terraform init \
  #     -backend-config="bucket=<tfstate-bucket>" \
  #     -backend-config="prefix=${var.project}/${var.env}"
  backend "gcs" {}
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

provider "google-beta" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

locals {
  prefix = "${var.project}-${var.env}"
  common_labels = merge(var.labels, {
    project     = var.project
    environment = var.env
    managed_by  = "terraform"
  })
}

# ── Enable required APIs ──────────────────────────────────────────────────────

resource "google_project_service" "apis" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
    "redis.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
    "secretmanager.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# ── VPC + Serverless VPC Connector (Cloud Run → Memorystore) ──────────────────

resource "google_compute_network" "llmops" {
  name                    = "${local.prefix}-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "llmops" {
  name          = "${local.prefix}-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.gcp_region
  network       = google_compute_network.llmops.id
}

resource "google_vpc_access_connector" "llmops" {
  name          = "${local.prefix}-vpc-conn"
  region        = var.gcp_region
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.llmops.name
  depends_on    = [google_project_service.apis]
}

# ── Service Account for Cloud Run ─────────────────────────────────────────────

resource "google_service_account" "gateway" {
  account_id   = "${local.prefix}-gateway-sa"
  display_name = "LLMOps Gateway Service Account (${var.env})"
}

resource "google_project_iam_member" "gateway_vertex_user" {
  project = var.gcp_project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.gateway.email}"
}

resource "google_project_iam_member" "gateway_storage_admin" {
  project = var.gcp_project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.gateway.email}"
}

resource "google_project_iam_member" "gateway_monitoring_writer" {
  project = var.gcp_project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.gateway.email}"
}

resource "google_project_iam_member" "gateway_log_writer" {
  project = var.gcp_project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.gateway.email}"
}

resource "google_project_iam_member" "gateway_secret_accessor" {
  project = var.gcp_project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.gateway.email}"
}

resource "google_project_iam_member" "gateway_ar_reader" {
  project = var.gcp_project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.gateway.email}"
}

# ── Artifact Registry ─────────────────────────────────────────────────────────

resource "google_artifact_registry_repository" "llmops" {
  location      = var.gcp_region
  repository_id = local.prefix
  description   = "LLMOps container images (${var.env})"
  format        = "DOCKER"
  labels        = local.common_labels
  depends_on    = [google_project_service.apis]
}

# ── Cloud Storage bucket (raw docs + model artifacts) ────────────────────────

resource "google_storage_bucket" "llmops" {
  name          = "${var.gcp_project_id}-${local.prefix}-data"
  location      = var.gcp_region
  force_destroy = var.env != "production"
  labels        = local.common_labels

  versioning {
    enabled = true
  }

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition { age = var.env == "production" ? 365 : 90 }
    action { type = "Delete" }
  }

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "gateway_storage" {
  bucket = google_storage_bucket.llmops.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.gateway.email}"
}

# ── Cloud Memorystore (Redis) ─────────────────────────────────────────────────

resource "google_redis_instance" "llmops" {
  name               = "${local.prefix}-redis"
  tier               = var.memorystore_tier
  memory_size_gb     = var.memorystore_size_gb
  region             = var.gcp_region
  authorized_network = google_compute_network.llmops.id
  redis_version      = "REDIS_7_0"
  display_name       = "LLMOps Redis (${var.env})"
  labels             = local.common_labels
  depends_on         = [google_project_service.apis]
}

# ── Vertex AI Vector Search index + endpoint ─────────────────────────────────
# NOTE: index creation can take 20-60 minutes on first apply.
# The deployed index endpoint is what the app queries at runtime.

resource "google_vertex_ai_index" "llmops" {
  provider     = google-beta
  display_name = "${local.prefix}-vector-index"
  region       = var.gcp_region
  labels       = local.common_labels

  metadata {
    contents_delta_uri = "gs://${google_storage_bucket.llmops.name}/vector-index-staging/"
    config {
      dimensions                  = var.vector_search_dimensions
      approximate_neighbors_count = 150
      distance_measure_type       = "DOT_PRODUCT_DISTANCE"
      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count    = 500
          leaf_nodes_to_search_percent = 7
        }
      }
    }
  }

  depends_on = [google_project_service.apis, google_storage_bucket.llmops]
}

resource "google_vertex_ai_index_endpoint" "llmops" {
  provider     = google-beta
  display_name = "${local.prefix}-vector-endpoint"
  region       = var.gcp_region
  labels       = local.common_labels
  network      = "projects/${data.google_project.current.number}/global/networks/${google_compute_network.llmops.name}"

  depends_on = [google_vertex_ai_index.llmops]
}

resource "google_vertex_ai_index_endpoint_deployed_index" "llmops" {
  provider         = google-beta
  index_endpoint   = google_vertex_ai_index_endpoint.llmops.id
  index            = google_vertex_ai_index.llmops.id
  deployed_index_id = replace("${local.prefix}_idx", "-", "_")
  display_name     = "${local.prefix} deployed index"

  dedicated_resources {
    machine_spec {
      machine_type = var.env == "production" ? "e2-standard-2" : "e2-standard-2"
    }
    min_replica_count = var.env == "production" ? 2 : 1
    max_replica_count = var.env == "production" ? 4 : 2
  }
}

data "google_project" "current" {
  project_id = var.gcp_project_id
}

# ── Cloud Run (gateway) ───────────────────────────────────────────────────────

resource "google_cloud_run_v2_service" "gateway" {
  name     = "${local.prefix}-gateway"
  location = var.gcp_region
  labels   = local.common_labels

  template {
    service_account = google_service_account.gateway.email

    vpc_access {
      connector = google_vpc_access_connector.llmops.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.cloud_run_max_instances
    }

    containers {
      image = var.gateway_image

      resources {
        limits = {
          cpu    = var.cloud_run_cpu
          memory = var.cloud_run_memory
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      ports {
        container_port = 4003
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.gcp_project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.gcp_region
      }
      env {
        name  = "VERTEX_MODEL_ID"
        value = var.gemini_model
      }
      env {
        name  = "VECTOR_SEARCH_INDEX_ENDPOINT"
        value = google_vertex_ai_index_endpoint.llmops.id
      }
      env {
        name  = "VECTOR_SEARCH_DEPLOYED_INDEX_ID"
        value = google_vertex_ai_index_endpoint_deployed_index.llmops.deployed_index_id
      }
      env {
        name  = "REDIS_HOST"
        value = google_redis_instance.llmops.host
      }
      env {
        name  = "REDIS_PORT"
        value = tostring(google_redis_instance.llmops.port)
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.llmops.name
      }

      startup_probe {
        http_get { path = "/health" }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get { path = "/health" }
        period_seconds    = 30
        failure_threshold = 3
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_vpc_access_connector.llmops,
    google_vertex_ai_index_endpoint_deployed_index.llmops,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.gateway.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── Secret Manager (Perspective API key, etc.) ────────────────────────────────

resource "google_secret_manager_secret" "perspective_api_key" {
  secret_id = "${local.prefix}-perspective-api-key"
  labels    = local.common_labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}
