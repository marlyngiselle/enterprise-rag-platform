# Every data plane sends its logs and metrics to the same workspace: query, indexing and
# model calls can be correlated with the API traces in Application Insights.
locals {
  diagnostic_targets = {
    search  = azurerm_search_service.this.id
    foundry = azapi_resource.foundry.id
    vault   = azurerm_key_vault.this.id
    blob    = "${azurerm_storage_account.documents.id}/blobServices/default"
  }
}

resource "azurerm_monitor_diagnostic_setting" "this" {
  for_each = local.diagnostic_targets

  name                       = "diag-to-log-analytics"
  target_resource_id         = each.value
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
