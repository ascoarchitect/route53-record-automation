# root/zones/subdomain.test-zone.com.tf

# Create delegation set
module "delegation_sets" {
  source  = "terraform-aws-modules/route53/aws//modules/delegation-sets"
  version = "~> 3.0"

  delegation_sets = {
    "subdomain_set" = {
      reference_name = "subdomain.test-zone.com"
    }
  }
}

# Create the subdomain zone using the delegation set
module "subdomain_zone" {
  source  = "terraform-aws-modules/route53/aws//modules/zones"
  version = "~> 3.0"

  zones = {
    "subdomain.test-zone.com" = {
      comment           = "Subdomain of test-zone.com managed by Terraform"
      delegation_set_id = module.delegation_sets.route53_delegation_set_id["subdomain_set"]
      tags              = var.common_tags
    }
  }

  depends_on = [module.delegation_sets]
}

# Configure the records for the subdomain
module "subdomain_zone_records" {
  source  = "terraform-aws-modules/route53/aws//modules/records"
  version = "~> 3.0"

  zone_name = "subdomain.test-zone.com"

  records = [
    {
      name    = ""
      type    = "A"
      ttl     = 300
      records = ["192.0.2.2"]
    },
    {
      name    = "www"
      type    = "CNAME"
      ttl     = 300
      records = ["subdomain.test-zone.com"]
    }
  ]

  depends_on = [module.subdomain_zone]
}

# Add NS records to the parent zone for delegation
module "delegation_records" {
  source  = "terraform-aws-modules/route53/aws//modules/records"
  version = "~> 3.0"

  zone_name = "test-zone.com"

  records = [
    {
      name    = "subdomain"
      type    = "NS"
      ttl     = 300
      records = module.subdomain_zone.route53_zone_name_servers["subdomain.test-zone.com"]
    }
  ]

  depends_on = [module.test_zone_com, module.subdomain_zone]
}