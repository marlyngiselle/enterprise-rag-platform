data "azurerm_client_config" "current" {}

# No Azure service in this design needs a secret. The vault exists for the credentials that
# cannot be avoided, such as a third party connector, and is RBAC only.
resource "azurerm_key_vault" "this" {
  name                          = local.names.key_vault
  location                      = azurerm_resource_group.this.location
  resource_group_name           = azurerm_resource_group.this.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = 90
  public_network_access_enabled = local.public_access
  tags                          = local.tags

  lifecycle {
    prevent_destroy = true
  }

  network_acls {
    default_action = local.public_access && length(var.allowed_ip_ranges) == 0 ? "Allow" : "Deny"
    bypass         = "AzureServices"
    ip_rules       = var.allowed_ip_ranges
  }
}
