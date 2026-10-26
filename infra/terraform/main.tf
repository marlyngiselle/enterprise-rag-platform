resource "azurerm_resource_group" "this" {
  name     = local.names.resource_group
  location = var.location
  tags     = local.tags
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = local.names.log_analytics
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days
  tags                = local.tags
}

# Workspace based, with local authentication disabled: telemetry is accepted only from
# identities holding Monitoring Metrics Publisher, never from a bare connection string.
resource "azurerm_application_insights" "this" {
  name                          = local.names.app_insights
  location                      = azurerm_resource_group.this.location
  resource_group_name           = azurerm_resource_group.this.name
  workspace_id                  = azurerm_log_analytics_workspace.this.id
  application_type              = "web"
  local_authentication_disabled = true
  tags                          = local.tags
}
