# Remote state in Azure Storage with Entra ID auth. Values are passed at init time:
#   terraform init -backend-config=backend.hcl
terraform {
  backend "azurerm" {
    use_azuread_auth = true
  }
}
