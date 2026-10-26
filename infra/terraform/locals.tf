resource "random_string" "suffix" {
  length  = 5
  lower   = true
  upper   = false
  numeric = true
  special = false
}

locals {
  base   = "${var.workload}-${var.environment}"
  suffix = random_string.suffix.result

  # Globally unique names carry a random suffix, so a rebuild never collides with a
  # soft deleted Key Vault or Foundry account that still holds the old name.
  names = {
    resource_group  = "rg-${local.base}"
    log_analytics   = "log-${local.base}"
    app_insights    = "appi-${local.base}"
    foundry         = "aif-${local.base}-${local.suffix}"
    project         = "proj-${local.base}"
    search          = "srch-${local.base}-${local.suffix}"
    storage         = substr("st${var.workload}${var.environment}${local.suffix}", 0, 24)
    key_vault       = substr("kv-${local.base}-${local.suffix}", 0, 24)
    vnet            = "vnet-${local.base}"
    api_identity    = "id-${local.base}-api"
    ingest_identity = "id-${local.base}-ingestion"
  }

  public_access = !var.enable_private_endpoints

  tags = merge(
    {
      workload    = var.workload
      environment = var.environment
      managed_by  = "terraform"
    },
    var.tags,
  )
}
