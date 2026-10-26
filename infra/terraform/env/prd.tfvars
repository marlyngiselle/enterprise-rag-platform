environment              = "prd"
location                 = "swedencentral"
search_sku               = "standard"
search_replica_count     = 3
search_partition_count   = 1
semantic_search_sku      = "standard"
enable_private_endpoints = true
vnet_address_space       = ["10.60.0.0/22"]
log_retention_days       = 90

chat_model = {
  name     = "gpt-4.1-mini"
  version  = "2025-04-14"
  sku      = "DataZoneStandard"
  capacity = 150
}

embedding_model = {
  name       = "text-embedding-3-large"
  version    = "1"
  sku        = "DataZoneStandard"
  capacity   = 150
  dimensions = 1536
}

tags = {
  cost_center = "platform"
}
