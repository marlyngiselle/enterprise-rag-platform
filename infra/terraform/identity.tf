# Two workload identities with different rights: the API only reads, ingestion only writes.
resource "azurerm_user_assigned_identity" "api" {
  name                = local.names.api_identity
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

resource "azurerm_user_assigned_identity" "ingestion" {
  name                = local.names.ingest_identity
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}
