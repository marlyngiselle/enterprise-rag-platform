variable "subscription_id" {
  description = "Target subscription. Passed through TF_VAR_subscription_id, never committed."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-fA-F-]{36}$", var.subscription_id))
    error_message = "subscription_id must be a GUID."
  }
}

variable "location" {
  description = "Azure region for every resource. Pick one where the chosen models have quota."
  type        = string
  default     = "swedencentral"
}

variable "environment" {
  description = "Environment name, used in resource names and tags."
  type        = string

  validation {
    condition     = contains(["dev", "tst", "prd"], var.environment)
    error_message = "environment must be dev, tst or prd."
  }
}

variable "workload" {
  description = "Short workload name used in resource names."
  type        = string
  default     = "rag"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{1,7}$", var.workload))
    error_message = "workload must be 2 to 8 lowercase letters or digits, starting with a letter."
  }
}

variable "chat_model" {
  description = "Chat model deployment. Capacity is in thousands of tokens per minute."
  type = object({
    deployment_name = optional(string, "chat")
    name            = string
    version         = string
    sku             = optional(string, "GlobalStandard")
    capacity        = optional(number, 50)
  })
  default = {
    name    = "gpt-4.1-mini"
    version = "2025-04-14"
  }

  validation {
    condition     = contains(["Standard", "GlobalStandard", "DataZoneStandard", "ProvisionedManaged"], var.chat_model.sku)
    error_message = "chat_model.sku must be Standard, GlobalStandard, DataZoneStandard or ProvisionedManaged."
  }

  validation {
    condition     = var.chat_model.capacity >= 1 && var.chat_model.capacity <= 1000
    error_message = "chat_model.capacity must be between 1 and 1000."
  }
}

variable "embedding_model" {
  description = "Embedding model deployment. dimensions must match the vector field of the index."
  type = object({
    deployment_name = optional(string, "embedding")
    name            = string
    version         = string
    sku             = optional(string, "GlobalStandard")
    capacity        = optional(number, 50)
    dimensions      = optional(number, 1536)
  })
  default = {
    name    = "text-embedding-3-large"
    version = "1"
  }

  validation {
    condition     = var.embedding_model.dimensions >= 256 && var.embedding_model.dimensions <= 3072
    error_message = "embedding_model.dimensions must be between 256 and 3072."
  }

  validation {
    condition     = var.embedding_model.capacity >= 1 && var.embedding_model.capacity <= 1000
    error_message = "embedding_model.capacity must be between 1 and 1000."
  }
}

variable "search_sku" {
  description = "Azure AI Search tier. The semantic ranker needs basic or higher."
  type        = string
  default     = "standard"

  validation {
    condition     = contains(["basic", "standard", "standard2", "standard3"], var.search_sku)
    error_message = "search_sku must be basic, standard, standard2 or standard3."
  }
}

variable "search_replica_count" {
  description = "Search replicas. Two give a read SLA, three give a read and write SLA."
  type        = number
  default     = 1

  validation {
    condition     = var.search_replica_count >= 1 && var.search_replica_count <= 12
    error_message = "search_replica_count must be between 1 and 12."
  }
}

variable "search_partition_count" {
  description = "Search partitions, for index size and indexing throughput."
  type        = number
  default     = 1

  validation {
    condition     = contains([1, 2, 3, 4, 6, 12], var.search_partition_count)
    error_message = "search_partition_count must be 1, 2, 3, 4, 6 or 12."
  }
}

variable "semantic_search_sku" {
  description = "Semantic ranker plan: free (limited queries per month) or standard."
  type        = string
  default     = "standard"

  validation {
    condition     = contains(["free", "standard"], var.semantic_search_sku)
    error_message = "semantic_search_sku must be free or standard."
  }
}

variable "enable_private_endpoints" {
  description = "Private endpoints and private DNS for every data plane, with public access disabled."
  type        = bool
  default     = true
}

variable "vnet_address_space" {
  description = "Address space of the workload VNet, used when private endpoints are enabled."
  type        = list(string)
  default     = ["10.60.0.0/22"]

  validation {
    condition     = alltrue([for cidr in var.vnet_address_space : can(cidrnetmask(cidr))])
    error_message = "vnet_address_space must contain valid IPv4 CIDR blocks."
  }
}

variable "allowed_ip_ranges" {
  description = "Public IPv4 ranges allowed on the data planes when private endpoints are disabled."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for cidr in var.allowed_ip_ranges : can(cidrnetmask(cidr)) || can(regex("^\\d+\\.\\d+\\.\\d+\\.\\d+$", cidr))])
    error_message = "allowed_ip_ranges must contain IPv4 addresses or CIDR blocks."
  }
}

variable "log_retention_days" {
  description = "Log Analytics retention in days."
  type        = number
  default     = 30

  validation {
    condition     = var.log_retention_days >= 30 && var.log_retention_days <= 730
    error_message = "log_retention_days must be between 30 and 730."
  }
}

variable "tags" {
  description = "Tags applied to every resource, merged with the default tags."
  type        = map(string)
  default     = {}
}
