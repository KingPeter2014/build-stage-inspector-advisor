variable "project" {
  description = "Project name used as prefix for resource names"
  type        = string
  default     = "llmops"
}

variable "env" {
  description = "Deployment environment"
  type        = string
  default     = "development"
  validation {
    condition     = contains(["development", "staging", "production"], var.env)
    error_message = "env must be development, staging, or production."
  }
}

variable "gcp_project_id" {
  description = "GCP project ID where all resources are created"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for all regional resources"
  type        = string
  default     = "us-central1"
}

variable "gateway_image" {
  description = "Full Artifact Registry image URI (e.g. us-central1-docker.pkg.dev/<project>/llmops/gateway:sha-abc123)"
  type        = string
}

variable "gemini_model" {
  description = "Vertex AI Gemini model ID used by the gateway"
  type        = string
  default     = "gemini-1.5-pro-002"
}

variable "vector_search_dimensions" {
  description = "Embedding dimension for the Vertex AI Vector Search index"
  type        = number
  default     = 768
}

variable "memorystore_tier" {
  description = "Cloud Memorystore Redis tier: BASIC or STANDARD_HA"
  type        = string
  default     = "BASIC"
}

variable "memorystore_size_gb" {
  description = "Cloud Memorystore Redis capacity in GB"
  type        = number
  default     = 1
}

variable "cloud_run_cpu" {
  description = "Cloud Run container CPU (e.g. '1' or '2')"
  type        = string
  default     = "1"
}

variable "cloud_run_memory" {
  description = "Cloud Run container memory (e.g. '512Mi', '1Gi', '2Gi')"
  type        = string
  default     = "1Gi"
}

variable "cloud_run_min_instances" {
  description = "Minimum Cloud Run instances (0 = scale-to-zero)"
  type        = number
  default     = 1
}

variable "cloud_run_max_instances" {
  description = "Maximum Cloud Run instances"
  type        = number
  default     = 10
}

variable "labels" {
  description = "GCP resource labels"
  type        = map(string)
  default     = {}
}
