# root/zones/testing-zone.com.tf

# Create the zone
module "testing_zone" {
  source  = "terraform-aws-modules/route53/aws//modules/zones"
  version = "~> 3.0"

  zones = {
    "testing-zone.com" = {
      comment = "Testing zone managed by Terraform"
      tags    = var.common_tags
    }
  }
}

# Create zone records
module "testing_zone_records" {
  source  = "terraform-aws-modules/route53/aws//modules/records"
  version = "~> 3.0"

  zone_name = "testing-zone.com"

  records = [
    {
      name    = ""  # apex record
      type    = "A"
      ttl     = 300
      records = ["192.0.2.3"]  # Replace with actual IP
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
      records = ["testing-zone.com"] # Replace with A or apex record
    },
    {
      name    = ""
      type    = "MX"
      ttl     = 3600
      records = [
        "10 mailserver1.testing-zone.com", # Replace with priority and mail server details
        "20 mailserver2.testing-zone.com"
      ]
    }
  ]

  depends_on = [module.testing_zone]
}