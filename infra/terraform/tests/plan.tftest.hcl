# Offline plan tests: providers are mocked, so no credentials and no Azure calls.
mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id = "00000000-0000-0000-0000-000000000000"
    }
  }
}

mock_provider "azapi" {}

mock_provider "random" {}

variables {
  subscription_id = "00000000-0000-0000-0000-000000000000"
  environment     = "dev"
}

run "private_by_default" {
  command = plan

  assert {
    condition     = length(azurerm_private_endpoint.this) == 4
    error_message = "Expected one private endpoint per data plane: search, foundry, blob, vault."
  }

  assert {
    condition     = length(azurerm_private_dns_zone.this) == 6
    error_message = "Expected six private DNS zones."
  }

  assert {
    condition     = azurerm_search_service.this.public_network_access_enabled == false
    error_message = "Search must not be public when private endpoints are enabled."
  }

  assert {
    condition     = azapi_resource.foundry.body.properties.publicNetworkAccess == "Disabled"
    error_message = "Foundry must not be public when private endpoints are enabled."
  }

  assert {
    condition     = azurerm_storage_account.documents.public_network_access_enabled == false && azurerm_key_vault.this.public_network_access_enabled == false
    error_message = "Storage and Key Vault must not be public when private endpoints are enabled."
  }
}

run "keyless_everywhere" {
  command = plan

  assert {
    condition     = azapi_resource.foundry.body.properties.disableLocalAuth == true
    error_message = "Foundry must have local auth disabled."
  }

  assert {
    condition     = azurerm_search_service.this.local_authentication_enabled == false
    error_message = "Search API keys must be disabled."
  }

  assert {
    condition     = azurerm_storage_account.documents.shared_access_key_enabled == false
    error_message = "Storage shared keys must be disabled."
  }

  assert {
    condition     = azurerm_application_insights.this.local_authentication_disabled == true
    error_message = "Application Insights must require Entra ID for ingestion."
  }
}

run "least_privilege_roles" {
  command = plan

  assert {
    condition     = length(azurerm_role_assignment.this) == 9
    error_message = "Expected nine role assignments."
  }

  assert {
    condition     = azurerm_role_assignment.this["api_search_reader"].role_definition_name == "Search Index Data Reader"
    error_message = "The API identity must only read the index."
  }

  assert {
    condition     = alltrue([for k, v in azurerm_role_assignment.this : v.role_definition_name != "Search Index Data Contributor" if startswith(k, "api_")])
    error_message = "The API identity must never write to the index."
  }

  assert {
    condition     = azurerm_role_assignment.this["ingestion_search_contributor"].role_definition_name == "Search Index Data Contributor"
    error_message = "The ingestion identity writes to the index."
  }
}

run "models_and_search_from_variables" {
  command = plan

  variables {
    chat_model = {
      name     = "gpt-4o-mini"
      version  = "2024-07-18"
      capacity = 10
    }
    search_sku = "standard2"
  }

  assert {
    condition     = azapi_resource.chat.body.properties.model.name == "gpt-4o-mini"
    error_message = "Chat model must come from var.chat_model."
  }

  assert {
    condition     = azapi_resource.embedding.body.properties.model.name == "text-embedding-3-large"
    error_message = "Embedding model default must be text-embedding-3-large."
  }

  assert {
    condition     = azurerm_search_service.this.sku == "standard2" && azurerm_search_service.this.semantic_search_sku == "standard"
    error_message = "Search sku and semantic ranker must follow the variables."
  }
}

run "public_mode_with_ip_allowlist" {
  command = plan

  variables {
    enable_private_endpoints = false
    allowed_ip_ranges        = ["203.0.113.10"]
  }

  assert {
    condition     = length(azurerm_private_endpoint.this) == 0 && length(azurerm_virtual_network.this) == 0
    error_message = "No network resources expected in public mode."
  }

  assert {
    condition     = azapi_resource.foundry.body.properties.networkAcls.defaultAction == "Deny"
    error_message = "With an allowlist the default action must be Deny."
  }

  assert {
    condition     = azurerm_search_service.this.allowed_ips == toset(["203.0.113.10"])
    error_message = "Search must carry the allowlist."
  }
}

run "rejects_bad_embedding_dimensions" {
  command = plan

  variables {
    embedding_model = {
      name       = "text-embedding-3-small"
      version    = "1"
      dimensions = 8192
    }
  }

  expect_failures = [var.embedding_model]
}

run "rejects_unknown_environment" {
  command = plan

  variables {
    environment = "staging"
  }

  expect_failures = [var.environment]
}
