terraform {
  required_version = ">= 1.7.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
  # Remote state in Azure Blob Storage.
  # Initialise with:
  #   terraform init \
  #     -backend-config="resource_group_name=<tfstate-rg>" \
  #     -backend-config="storage_account_name=<tfstate-sa>" \
  #     -backend-config="container_name=tfstate" \
  #     -backend-config="key=${var.project}-${var.env}.tfstate"
  backend "azurerm" {}
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
  }
}

locals {
  prefix = "${var.project}-${var.env}"
  # Storage account names must be globally unique, 3-24 chars, alphanumeric only
  sa_name = "${replace(var.project, "-", "")}${var.env}sa"

  common_tags = merge(var.tags, {
    project     = var.project
    environment = var.env
    managed_by  = "terraform"
  })
}

data "azurerm_client_config" "current" {}

# ── Resource group ─────────────────────────────────────────────────────────────

resource "azurerm_resource_group" "llmops" {
  name     = "${local.prefix}-rg"
  location = var.location
  tags     = local.common_tags
}

# ── Key Vault (secrets: API keys, Redis password, etc.) ───────────────────────

resource "azurerm_key_vault" "llmops" {
  name                       = "${local.prefix}-kv"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.llmops.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  purge_protection_enabled   = var.env == "production"
  soft_delete_retention_days = 7
  tags                       = local.common_tags
}

resource "azurerm_key_vault_access_policy" "deployer" {
  key_vault_id = azurerm_key_vault.llmops.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id
  secret_permissions = ["Get", "List", "Set", "Delete", "Purge"]
}

# ── Container Registry (ACR) ──────────────────────────────────────────────────

resource "azurerm_container_registry" "llmops" {
  name                = "${replace(local.prefix, "-", "")}acr"
  resource_group_name = azurerm_resource_group.llmops.name
  location            = var.location
  sku                 = "Standard"
  admin_enabled       = false  # use Managed Identity, not admin credentials
  tags                = local.common_tags
}

# ── Azure OpenAI Service ───────────────────────────────────────────────────────

resource "azurerm_cognitive_account" "openai" {
  name                = "${local.prefix}-oai"
  location            = var.location
  resource_group_name = azurerm_resource_group.llmops.name
  kind                = "OpenAI"
  sku_name            = "S0"
  tags                = local.common_tags
}

resource "azurerm_cognitive_deployment" "gpt4o" {
  name                 = "gpt-4o"
  cognitive_account_id = azurerm_cognitive_account.openai.id
  model {
    format  = "OpenAI"
    name    = "gpt-4o"
    version = "2024-11-20"
  }
  scale {
    type     = "Standard"
    capacity = var.gpt4o_capacity_tpm
  }
}

resource "azurerm_cognitive_deployment" "embedding" {
  name                 = "text-embedding-3-small"
  cognitive_account_id = azurerm_cognitive_account.openai.id
  model {
    format  = "OpenAI"
    name    = "text-embedding-3-small"
    version = "1"
  }
  scale {
    type     = "Standard"
    capacity = var.embedding_capacity_tpm
  }
}

# ── Azure AI Search ───────────────────────────────────────────────────────────

resource "azurerm_search_service" "llmops" {
  name                = "${local.prefix}-search"
  resource_group_name = azurerm_resource_group.llmops.name
  location            = var.location
  sku                 = var.search_sku
  replica_count       = var.env == "production" ? 2 : 1
  partition_count     = 1
  tags                = local.common_tags
}

# ── Azure Cache for Redis ─────────────────────────────────────────────────────

resource "azurerm_redis_cache" "llmops" {
  name                = "${local.prefix}-redis"
  location            = var.location
  resource_group_name = azurerm_resource_group.llmops.name
  capacity            = var.redis_capacity
  family              = "C"
  sku_name            = var.env == "production" ? "Standard" : "Basic"
  enable_non_ssl_port = false
  minimum_tls_version = "1.2"
  tags                = local.common_tags

  redis_configuration {
    maxmemory_policy = "allkeys-lru"
  }
}

# ── Storage Account (ADLS Gen2 for raw docs + ingestion staging) ──────────────

resource "azurerm_storage_account" "llmops" {
  name                     = local.sa_name
  resource_group_name      = azurerm_resource_group.llmops.name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = var.env == "production" ? "ZRS" : "LRS"
  is_hns_enabled           = true   # ADLS Gen2
  min_tls_version          = "TLS1_2"
  tags                     = local.common_tags
}

resource "azurerm_storage_container" "raw_docs" {
  name                  = "raw-docs"
  storage_account_name  = azurerm_storage_account.llmops.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "model_artifacts" {
  name                  = "model-artifacts"
  storage_account_name  = azurerm_storage_account.llmops.name
  container_access_type = "private"
}

# ── Log Analytics + Application Insights ─────────────────────────────────────

resource "azurerm_log_analytics_workspace" "llmops" {
  name                = "${local.prefix}-law"
  location            = var.location
  resource_group_name = azurerm_resource_group.llmops.name
  sku                 = "PerGB2018"
  retention_in_days   = var.env == "production" ? 90 : 30
  tags                = local.common_tags
}

resource "azurerm_application_insights" "llmops" {
  name                = "${local.prefix}-appinsights"
  location            = var.location
  resource_group_name = azurerm_resource_group.llmops.name
  workspace_id        = azurerm_log_analytics_workspace.llmops.id
  application_type    = "web"
  tags                = local.common_tags
}

# ── Azure ML Workspace (experiment tracking + model registry) ─────────────────

resource "azurerm_machine_learning_workspace" "llmops" {
  name                    = "${local.prefix}-aml"
  location                = var.location
  resource_group_name     = azurerm_resource_group.llmops.name
  application_insights_id = azurerm_application_insights.llmops.id
  key_vault_id            = azurerm_key_vault.llmops.id
  storage_account_id      = azurerm_storage_account.llmops.id
  tags                    = local.common_tags

  identity {
    type = "SystemAssigned"
  }
}

# ── Container Apps Environment + Gateway ─────────────────────────────────────

resource "azurerm_container_app_environment" "llmops" {
  name                       = "${local.prefix}-cae"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.llmops.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.llmops.id
  tags                       = local.common_tags
}

resource "azurerm_container_app" "gateway" {
  name                         = "${local.prefix}-gateway"
  container_app_environment_id = azurerm_container_app_environment.llmops.id
  resource_group_name          = azurerm_resource_group.llmops.name
  revision_mode                = "Single"
  tags                         = local.common_tags

  identity {
    type = "SystemAssigned"
  }

  template {
    min_replicas = var.gateway_min_replicas
    max_replicas = var.gateway_max_replicas

    container {
      name   = "gateway"
      image  = var.gateway_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = azurerm_cognitive_account.openai.endpoint
      }
      env {
        name  = "AZURE_AI_SEARCH_ENDPOINT"
        value = "https://${azurerm_search_service.llmops.name}.search.windows.net"
      }
      env {
        name  = "REDIS_URL"
        value = "rediss://:${azurerm_redis_cache.llmops.primary_access_key}@${azurerm_redis_cache.llmops.hostname}:${azurerm_redis_cache.llmops.ssl_port}"
      }
      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.llmops.connection_string
      }
      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = azurerm_storage_account.llmops.name
      }

      liveness_probe {
        path             = "/health"
        port             = 4001
        transport        = "HTTP"
        initial_delay    = 10
        interval_seconds = 30
      }
      readiness_probe {
        path             = "/health"
        port             = 4001
        transport        = "HTTP"
        interval_seconds = 10
      }
    }

    http_scale_rule {
      name                = "http-scaler"
      concurrent_requests = "100"
    }
  }

  ingress {
    external_enabled = true
    target_port      = 4001
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}

# ── Role assignments (Managed Identity → Azure services) ──────────────────────

resource "azurerm_role_assignment" "gateway_oai_user" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_container_app.gateway.identity[0].principal_id
}

resource "azurerm_role_assignment" "gateway_search_contributor" {
  scope                = azurerm_search_service.llmops.id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = azurerm_container_app.gateway.identity[0].principal_id
}

resource "azurerm_role_assignment" "gateway_search_reader" {
  scope                = azurerm_search_service.llmops.id
  role_definition_name = "Search Service Contributor"
  principal_id         = azurerm_container_app.gateway.identity[0].principal_id
}

resource "azurerm_role_assignment" "gateway_storage_blob" {
  scope                = azurerm_storage_account.llmops.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_container_app.gateway.identity[0].principal_id
}

resource "azurerm_role_assignment" "gateway_acr_pull" {
  scope                = azurerm_container_registry.llmops.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_container_app.gateway.identity[0].principal_id
}

resource "azurerm_role_assignment" "gateway_kv_secrets" {
  scope                = azurerm_key_vault.llmops.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_container_app.gateway.identity[0].principal_id
}
