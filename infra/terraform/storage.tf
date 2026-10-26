# Landing zone for source documents. Shared keys are disabled, so every read and write is an
# Entra ID call that shows up in the audit log with the caller's identity.
resource "azurerm_storage_account" "documents" {
  name                              = local.names.storage
  location                          = azurerm_resource_group.this.location
  resource_group_name               = azurerm_resource_group.this.name
  account_tier                      = "Standard"
  account_replication_type          = var.environment == "prd" ? "ZRS" : "LRS"
  account_kind                      = "StorageV2"
  min_tls_version                   = "TLS1_2"
  https_traffic_only_enabled        = true
  shared_access_key_enabled         = false
  default_to_oauth_authentication   = true
  allow_nested_items_to_be_public   = false
  public_network_access_enabled     = local.public_access
  infrastructure_encryption_enabled = true
  tags                              = local.tags

  lifecycle {
    prevent_destroy = true
  }

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 30
    }

    container_delete_retention_policy {
      days = 30
    }
  }

  network_rules {
    default_action = local.public_access && length(var.allowed_ip_ranges) == 0 ? "Allow" : "Deny"
    bypass         = ["AzureServices"]
    ip_rules       = var.allowed_ip_ranges
  }
}

resource "azurerm_storage_container" "documents" {
  name                  = "documents"
  storage_account_id    = azurerm_storage_account.documents.id
  container_access_type = "private"

  lifecycle {
    prevent_destroy = true
  }
}
