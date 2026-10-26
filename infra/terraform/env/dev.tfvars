environment              = "dev"
location                 = "swedencentral"
search_sku               = "basic"
search_replica_count     = 1
semantic_search_sku      = "free"
enable_private_endpoints = false
allowed_ip_ranges        = ["203.0.113.10"]

chat_model = {
  name     = "gpt-4.1-mini"
  version  = "2025-04-14"
  capacity = 30
}

embedding_model = {
  name       = "text-embedding-3-large"
  version    = "1"
  capacity   = 30
  dimensions = 1536
}

tags = {
  cost_center = "platform"
}
