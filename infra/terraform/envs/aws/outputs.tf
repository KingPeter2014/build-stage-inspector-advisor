output "alb_dns_name" {
  description = "ALB DNS name — point your domain CNAME here or use directly"
  value       = aws_lb.llmops.dns_name
}

output "ecr_repository_url" {
  description = "ECR repository URL — use in CI to tag and push gateway images"
  value       = aws_ecr_repository.gateway.repository_url
}

output "opensearch_endpoint" {
  description = "OpenSearch domain endpoint — set as OPENSEARCH_ENDPOINT in app config"
  value       = "https://${aws_opensearch_domain.llmops.endpoint}"
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint — set as REDIS_URL in app config"
  value       = "redis://${aws_elasticache_cluster.llmops.cache_nodes[0].address}:6379"
}

output "s3_bucket_name" {
  description = "S3 bucket name for raw docs and model artifacts"
  value       = aws_s3_bucket.llmops.bucket
}

output "ecs_cluster_name" {
  description = "ECS cluster name — used in deploy step: aws ecs update-service"
  value       = aws_ecs_cluster.llmops.name
}

output "ecs_service_name" {
  description = "ECS service name — used in deploy step"
  value       = aws_ecs_service.gateway.name
}

output "ecs_task_role_arn" {
  description = "ECS task IAM role ARN"
  value       = aws_iam_role.ecs_task.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for gateway container logs"
  value       = aws_cloudwatch_log_group.gateway.name
}
