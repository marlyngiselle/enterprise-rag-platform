locals {
  role_assignments = {
    api_search_reader = {
      scope     = azurerm_search_service.this.id
      role      = "Search Index Data Reader"
      principal = azurerm_user_assigned_identity.api.principal_id
    }
    api_openai_user = {
      scope     = azapi_resource.foundry.id
      role      = "Cognitive Services OpenAI User"
      principal = azurerm_user_assigned_identity.api.principal_id
    }
    api_kv_secrets_user = {
      scope     = azurerm_key_vault.this.id
      role      = "Key Vault Secrets User"
      principal = azurerm_user_assigned_identity.api.principal_id
    }
    api_metrics_publisher = {
      scope     = azurerm_application_insights.this.id
      role      = "Monitoring Metrics Publisher"
      principal = azurerm_user_assigned_identity.api.principal_id
    }
    ingestion_search_contributor = {
      scope     = azurerm_search_service.this.id
      role      = "Search Index Data Contributor"
      principal = azurerm_user_assigned_identity.ingestion.principal_id
    }
    ingestion_search_service = {
      scope     = azurerm_search_service.this.id
      role      = "Search Service Contributor"
      principal = azurerm_user_assigned_identity.ingestion.principal_id
    }
    ingestion_openai_user = {
      scope     = azapi_resource.foundry.id
      role      = "Cognitive Services OpenAI User"
      principal = azurerm_user_assigned_identity.ingestion.principal_id
    }
    ingestion_blob_reader = {
      scope     = azurerm_storage_container.documents.id
      role      = "Storage Blob Data Reader"
      principal = azurerm_user_assigned_identity.ingestion.principal_id
    }
    ingestion_metrics_publisher = {
      scope     = azurerm_application_insights.this.id
      role      = "Monitoring Metrics Publisher"
      principal = azurerm_user_assigned_identity.ingestion.principal_id
    }
  }
}

resource "azurerm_role_assignment" "this" {
  for_each = local.role_assignments

  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_id         = each.value.principal
  principal_type       = "ServicePrincipal"
  description          = "enterprise-rag: ${each.key}"
}
