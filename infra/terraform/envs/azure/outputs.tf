output "resource_group_name" {
  description = "Resource group containing all LLMOps resources"
  value       = azurerm_resource_group.llmops.name
}

output "gateway_url" {
  description = "Public FQDN of the gateway Container App"
  value       = "https://${azurerm_container_app.gateway.ingress[0].fqdn}"
}

output "acr_login_server" {
  description = "Azure Container Registry login server (use in CI to tag/push images)"
  value       = azurerm_container_registry.llmops.login_server
}

output "openai_endpoint" {
  description = "Azure OpenAI endpoint URL — set as AZURE_OPENAI_ENDPOINT in app config"
  value       = azurerm_cognitive_account.openai.endpoint
}

output "ai_search_endpoint" {
  description = "Azure AI Search endpoint URL — set as AZURE_AI_SEARCH_ENDPOINT in app config"
  value       = "https://${azurerm_search_service.llmops.name}.search.windows.net"
}

output "ai_search_admin_key" {
  description = "Azure AI Search admin key — store in Key Vault, do not log"
  value       = azurerm_search_service.llmops.primary_key
  sensitive   = true
}

output "storage_account_name" {
  description = "ADLS Gen2 storage account name"
  value       = azurerm_storage_account.llmops.name
}

output "redis_hostname" {
  description = "Redis cache hostname"
  value       = azurerm_redis_cache.llmops.hostname
}

output "redis_ssl_port" {
  description = "Redis SSL port"
  value       = azurerm_redis_cache.llmops.ssl_port
}

output "redis_primary_key" {
  description = "Redis primary access key — store in Key Vault"
  value       = azurerm_redis_cache.llmops.primary_access_key
  sensitive   = true
}

output "app_insights_connection_string" {
  description = "Application Insights connection string — set as APPLICATIONINSIGHTS_CONNECTION_STRING"
  value       = azurerm_application_insights.llmops.connection_string
  sensitive   = true
}

output "aml_workspace_name" {
  description = "Azure ML workspace name for experiment tracking"
  value       = azurerm_machine_learning_workspace.llmops.name
}

output "key_vault_uri" {
  description = "Key Vault URI for secret references"
  value       = azurerm_key_vault.llmops.vault_uri
}

output "gateway_principal_id" {
  description = "Managed Identity principal ID of the gateway Container App"
  value       = azurerm_container_app.gateway.identity[0].principal_id
}
