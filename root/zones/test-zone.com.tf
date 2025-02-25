# root/zones/test-zone.com.tf

# Create the zone
module "test_zone_com" {
  source  = "terraform-aws-modules/route53/aws//modules/zones"
  version = "~> 3.0"
  zones = {
    "test-zone.com" = {
      comment = "Test zone managed by Terraform"
      tags = merge(
        var.common_tags,
        {
          Environment = var.environment
          Purpose = "testing"
        }
      )
    }
  }
}

# Create zone records
module "test_zone_com_records" {
  source  = "terraform-aws-modules/route53/aws//modules/records"
  version = "~> 3.0"
  
  zone_name = "test-zone.com"
  
  records = [
    {
      name    = ""
      type    = "A"
      ttl     = 300
      records = ["192.0.2.1"]  # Replace with actual IP
    },
    {
      name    = "wwws"
      type    = "A"
      ttl     = 300
      records = ["192.0.2.5"]  # Replace with actual IP
    },
    {
      name    = "www"
      type    = "CNAME"
      ttl     = 300
      records = ["test-zone.com"] # Replace with A or apex record
    },
    {
      name    = ""
      type    = "MX"
      ttl     = 3600
      records = [
        "10 mailserver1.test-zone.com", # Replace with priority and mail server details
        "20 mailserver2.test-zone.com"
      ]
    }
  ]

  depends_on = [module.test_zone_com]
}