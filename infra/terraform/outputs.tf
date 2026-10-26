output "resource_group_name" {
  description = "Resource group holding the platform."
  value       = azurerm_resource_group.this.name
}

output "openai_endpoint" {
  description = "Azure OpenAI endpoint of the Foundry resource, for RAG_OPENAI_ENDPOINT."
  value       = "https://${local.names.foundry}.openai.azure.com/"
}

output "foundry_project_id" {
  description = "Resource id of the Foundry project."
  value       = azapi_resource.project.id
}

output "search_endpoint" {
  description = "Azure AI Search endpoint, for RAG_SEARCH_ENDPOINT."
  value       = "https://${azurerm_search_service.this.name}.search.windows.net"
}

output "chat_deployment_name" {
  description = "Chat deployment name, for RAG_CHAT_DEPLOYMENT."
  value       = azapi_resource.chat.name
}

output "embedding_deployment_name" {
  description = "Embedding deployment name, for RAG_EMBEDDING_DEPLOYMENT."
  value       = azapi_resource.embedding.name
}

output "embedding_dimensions" {
  description = "Vector size the index must use, for RAG_EMBEDDING_DIMENSIONS."
  value       = var.embedding_model.dimensions
}

output "api_identity_client_id" {
  description = "Client id of the read only API identity, for AZURE_CLIENT_ID."
  value       = azurerm_user_assigned_identity.api.client_id
}

output "ingestion_identity_client_id" {
  description = "Client id of the ingestion identity, for AZURE_CLIENT_ID in the ingestion job."
  value       = azurerm_user_assigned_identity.ingestion.client_id
}

output "documents_container_id" {
  description = "Resource id of the documents container."
  value       = azurerm_storage_container.documents.id
}

output "key_vault_uri" {
  description = "Key Vault URI."
  value       = azurerm_key_vault.this.vault_uri
}

output "app_insights_connection_string" {
  description = "Application Insights connection string, for APPLICATIONINSIGHTS_CONNECTION_STRING."
  value       = azurerm_application_insights.this.connection_string
  sensitive   = true
}

output "private_endpoints" {
  description = "Private endpoints created, by data plane."
  value       = sort(keys(azurerm_private_endpoint.this))
}
