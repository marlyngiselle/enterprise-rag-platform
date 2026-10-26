# Azure AI Foundry resource (Cognitive Services account of kind AIServices) with a project.
# Declared with azapi because project management on the account is newer than the azurerm
# schema. Local auth is disabled: every caller authenticates with Entra ID.
resource "azapi_resource" "foundry" {
  type      = "Microsoft.CognitiveServices/accounts@2025-06-01"
  name      = local.names.foundry
  parent_id = azurerm_resource_group.this.id
  location  = var.location
  tags      = local.tags

  identity {
    type = "SystemAssigned"
  }

  body = {
    kind = "AIServices"
    sku = {
      name = "S0"
    }
    properties = {
      customSubDomainName    = local.names.foundry
      allowProjectManagement = true
      disableLocalAuth       = true
      publicNetworkAccess    = local.public_access ? "Enabled" : "Disabled"
      networkAcls = {
        defaultAction       = local.public_access && length(var.allowed_ip_ranges) == 0 ? "Allow" : "Deny"
        ipRules             = [for ip in var.allowed_ip_ranges : { value = ip }]
        virtualNetworkRules = []
      }
    }
  }

  response_export_values = ["properties.endpoint"]
}

resource "azapi_resource" "project" {
  type      = "Microsoft.CognitiveServices/accounts/projects@2025-06-01"
  name      = local.names.project
  parent_id = azapi_resource.foundry.id
  location  = var.location
  tags      = local.tags

  identity {
    type = "SystemAssigned"
  }

  body = {
    properties = {
      displayName = "Enterprise RAG (${var.environment})"
      description = "Grounded question answering over the internal knowledge base."
    }
  }
}

resource "azapi_resource" "chat" {
  type      = "Microsoft.CognitiveServices/accounts/deployments@2025-06-01"
  name      = var.chat_model.deployment_name
  parent_id = azapi_resource.foundry.id

  body = {
    sku = {
      name     = var.chat_model.sku
      capacity = var.chat_model.capacity
    }
    properties = {
      model = {
        format  = "OpenAI"
        name    = var.chat_model.name
        version = var.chat_model.version
      }
      versionUpgradeOption = "NoAutoUpgrade"
      raiPolicyName        = "Microsoft.DefaultV2"
    }
  }
}

# Deployments on one account are serialised: parallel writes fail with a conflict.
resource "azapi_resource" "embedding" {
  type      = "Microsoft.CognitiveServices/accounts/deployments@2025-06-01"
  name      = var.embedding_model.deployment_name
  parent_id = azapi_resource.foundry.id

  body = {
    sku = {
      name     = var.embedding_model.sku
      capacity = var.embedding_model.capacity
    }
    properties = {
      model = {
        format  = "OpenAI"
        name    = var.embedding_model.name
        version = var.embedding_model.version
      }
      versionUpgradeOption = "NoAutoUpgrade"
    }
  }

  depends_on = [azapi_resource.chat]
}
