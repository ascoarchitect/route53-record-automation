# root/main.tf

locals {
  common_tags = merge(
    var.default_tags,
    {
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}

# This ensures all .tf files in the zones directory are included
module "zones" {
  source = "./zones"

  # Pass through the common variables needed by zone configurations
  environment = var.environment
  common_tags = local.common_tags
}