variable "project" {
  description = "Project name used as prefix for all resource names"
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

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus2"
}

variable "gateway_image" {
  description = "Full image URI for the gateway container app (e.g. myacr.azurecr.io/llmops-gateway:sha-abc123)"
  type        = string
}

variable "gpt4o_capacity_tpm" {
  description = "Azure OpenAI gpt-4o capacity in thousands of tokens-per-minute"
  type        = number
  default     = 30
}

variable "embedding_capacity_tpm" {
  description = "Azure OpenAI text-embedding-3-small capacity in thousands of TPM"
  type        = number
  default     = 120
}

variable "search_sku" {
  description = "Azure AI Search SKU: free | basic | standard | standard2 | standard3"
  type        = string
  default     = "standard"
}

variable "redis_capacity" {
  description = "Redis cache capacity (0=250MB, 1=1GB, 2=2.5GB, 3=6GB, 4=13GB, 5=26GB, 6=53GB)"
  type        = number
  default     = 1
}

variable "gateway_min_replicas" {
  description = "Minimum Container App replicas (0 = scale-to-zero)"
  type        = number
  default     = 1
}

variable "gateway_max_replicas" {
  description = "Maximum Container App replicas"
  type        = number
  default     = 10
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
