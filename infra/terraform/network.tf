# Private networking, created only when enable_private_endpoints is true. Every data plane
# (search, models, documents, secrets) gets a private endpoint and a private DNS zone, and
# public network access is disabled on each resource.
locals {
  dns_zones = var.enable_private_endpoints ? toset([
    "privatelink.search.windows.net",
    "privatelink.openai.azure.com",
    "privatelink.cognitiveservices.azure.com",
    "privatelink.services.ai.azure.com",
    "privatelink.blob.core.windows.net",
    "privatelink.vaultcore.azure.net",
  ]) : toset([])

  private_endpoints = var.enable_private_endpoints ? {
    search = {
      resource_id = azurerm_search_service.this.id
      subresource = "searchService"
      zones       = ["privatelink.search.windows.net"]
    }
    foundry = {
      resource_id = azapi_resource.foundry.id
      subresource = "account"
      zones = [
        "privatelink.openai.azure.com",
        "privatelink.cognitiveservices.azure.com",
        "privatelink.services.ai.azure.com",
      ]
    }
    blob = {
      resource_id = azurerm_storage_account.documents.id
      subresource = "blob"
      zones       = ["privatelink.blob.core.windows.net"]
    }
    vault = {
      resource_id = azurerm_key_vault.this.id
      subresource = "vault"
      zones       = ["privatelink.vaultcore.azure.net"]
    }
  } : {}
}

resource "azurerm_virtual_network" "this" {
  count = var.enable_private_endpoints ? 1 : 0

  name                = local.names.vnet
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  address_space       = var.vnet_address_space
  tags                = local.tags
}

resource "azurerm_subnet" "private_endpoints" {
  count = var.enable_private_endpoints ? 1 : 0

  name                              = "snet-private-endpoints"
  resource_group_name               = azurerm_resource_group.this.name
  virtual_network_name              = azurerm_virtual_network.this[0].name
  address_prefixes                  = [cidrsubnet(var.vnet_address_space[0], 4, 0)]
  private_endpoint_network_policies = "Enabled"
}

# Workload subnet for the API and the ingestion job (Container Apps environment).
resource "azurerm_subnet" "workload" {
  count = var.enable_private_endpoints ? 1 : 0

  name                 = "snet-workload"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this[0].name
  address_prefixes     = [cidrsubnet(var.vnet_address_space[0], 1, 1)]

  delegation {
    name = "container-apps"

    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_network_security_group" "private_endpoints" {
  count = var.enable_private_endpoints ? 1 : 0

  name                = "nsg-${local.base}-private-endpoints"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags

  security_rule {
    name                       = "allow-https-from-vnet"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "VirtualNetwork"
  }

  security_rule {
    name                       = "deny-all-inbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "private_endpoints" {
  count = var.enable_private_endpoints ? 1 : 0

  subnet_id                 = azurerm_subnet.private_endpoints[0].id
  network_security_group_id = azurerm_network_security_group.private_endpoints[0].id
}

resource "azurerm_private_dns_zone" "this" {
  for_each = local.dns_zones

  name                = each.value
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "this" {
  for_each = local.dns_zones

  name                  = "link-${local.base}"
  resource_group_name   = azurerm_resource_group.this.name
  private_dns_zone_name = azurerm_private_dns_zone.this[each.key].name
  virtual_network_id    = azurerm_virtual_network.this[0].id
  registration_enabled  = false
  tags                  = local.tags
}

resource "azurerm_private_endpoint" "this" {
  for_each = local.private_endpoints

  name                = "pe-${local.base}-${each.key}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  subnet_id           = azurerm_subnet.private_endpoints[0].id
  tags                = local.tags

  private_service_connection {
    name                           = "psc-${local.base}-${each.key}"
    private_connection_resource_id = each.value.resource_id
    subresource_names              = [each.value.subresource]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [for zone in each.value.zones : azurerm_private_dns_zone.this[zone].id]
  }
}
