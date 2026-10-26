# Azure AI Search with the semantic ranker. API keys are disabled: the API reads with
# Search Index Data Reader, the ingestion job writes with Search Index Data Contributor.
resource "azurerm_search_service" "this" {
  name                          = local.names.search
  location                      = azurerm_resource_group.this.location
  resource_group_name           = azurerm_resource_group.this.name
  sku                           = var.search_sku
  replica_count                 = var.search_replica_count
  partition_count               = var.search_partition_count
  semantic_search_sku           = var.semantic_search_sku
  local_authentication_enabled  = false
  public_network_access_enabled = local.public_access
  allowed_ips                   = local.public_access ? var.allowed_ip_ranges : []
  network_rule_bypass_option    = "AzureServices"
  tags                          = local.tags

  identity {
    type = "SystemAssigned"
  }
}
