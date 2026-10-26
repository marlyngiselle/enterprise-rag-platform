provider "azurerm" {
  subscription_id     = var.subscription_id
  storage_use_azuread = true

  features {
    cognitive_account {
      purge_soft_delete_on_destroy = false
    }

    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }

    resource_group {
      prevent_deletion_if_contains_resources = true
    }
  }
}

provider "azapi" {
  subscription_id = var.subscription_id
}
