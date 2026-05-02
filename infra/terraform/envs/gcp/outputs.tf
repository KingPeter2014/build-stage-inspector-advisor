output "gateway_url" {
  description = "Cloud Run gateway URL — use as the API base URL"
  value       = google_cloud_run_v2_service.gateway.uri
}

output "artifact_registry_url" {
  description = "Artifact Registry URL — use in CI to tag and push images"
  value       = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.llmops.repository_id}"
}

output "gcs_bucket_name" {
  description = "GCS bucket for raw docs and model artifacts"
  value       = google_storage_bucket.llmops.name
}

output "redis_host" {
  description = "Memorystore Redis host — set as REDIS_HOST in app config"
  value       = google_redis_instance.llmops.host
}

output "redis_port" {
  description = "Memorystore Redis port"
  value       = google_redis_instance.llmops.port
}

output "vector_index_id" {
  description = "Vertex AI Vector Search index ID"
  value       = google_vertex_ai_index.llmops.id
}

output "vector_index_endpoint_id" {
  description = "Vertex AI Vector Search index endpoint ID — set as VECTOR_SEARCH_INDEX_ENDPOINT"
  value       = google_vertex_ai_index_endpoint.llmops.id
}

output "vector_deployed_index_id" {
  description = "Deployed index ID — set as VECTOR_SEARCH_DEPLOYED_INDEX_ID"
  value       = google_vertex_ai_index_endpoint_deployed_index.llmops.deployed_index_id
}

output "gateway_service_account" {
  description = "Service account email used by the Cloud Run gateway"
  value       = google_service_account.gateway.email
}

output "vpc_connector_id" {
  description = "Serverless VPC connector ID (used for private Redis access)"
  value       = google_vpc_access_connector.llmops.id
}
