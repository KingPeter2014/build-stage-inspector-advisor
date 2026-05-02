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

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "gateway_image" {
  description = "Full ECR image URI for the gateway task (e.g. 123456789.dkr.ecr.us-east-1.amazonaws.com/llmops-gateway:sha-abc123)"
  type        = string
}

variable "bedrock_model_id" {
  description = "Default Bedrock model ID for the gateway"
  type        = string
  default     = "anthropic.claude-3-5-sonnet-20241022-v2:0"
}

variable "opensearch_instance_type" {
  description = "OpenSearch data node instance type"
  type        = string
  default     = "t3.medium.search"
}

variable "opensearch_instance_count" {
  description = "Number of OpenSearch data nodes"
  type        = number
  default     = 1
}

variable "opensearch_volume_size_gb" {
  description = "EBS volume size per OpenSearch node in GB"
  type        = number
  default     = 20
}

variable "elasticache_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t4g.micro"
}

variable "ecs_cpu" {
  description = "Fargate task CPU units (256=0.25vCPU, 512=0.5vCPU, 1024=1vCPU)"
  type        = number
  default     = 512
}

variable "ecs_memory_mb" {
  description = "Fargate task memory in MiB"
  type        = number
  default     = 1024
}

variable "ecs_desired_count" {
  description = "Desired number of gateway ECS tasks"
  type        = number
  default     = 1
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
