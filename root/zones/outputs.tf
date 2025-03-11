# root/zones/outputs.tf

# Output test-zone.com details
output "test_zone_com" {
  description = "Details for test-zone.com"
  value = {
    zone_id      = module.test_zone_com.route53_zone_zone_id["test-zone.com"]
    name_servers = module.test_zone_com.route53_zone_name_servers["test-zone.com"]
    records      = module.test_zone_com_records.route53_record_name
  }
}

# Output testing-zone.com details
output "testing_zone_com" {
  description = "Details for testing-zone.com"
  value = {
    zone_id      = module.testing_zone.route53_zone_zone_id["testing-zone.com"]
    name_servers = module.testing_zone.route53_zone_name_servers["testing-zone.com"]
    records      = module.testing_zone_records.route53_record_name
  }
}

# Output subdomain.test-zone.com details (if it exists)
output "subdomain_test_zone_com" {
  description = "Details for subdomain.test-zone.com"
  value = {
    zone_id      = module.subdomain_zone.route53_zone_zone_id["subdomain.test-zone.com"]
    name_servers = module.subdomain_zone.route53_zone_name_servers["subdomain.test-zone.com"]
    records      = module.subdomain_zone_records.route53_record_name
  }
}

# Combined output of all zones
output "all_zones" {
  description = "Combined information for all zones"
  value = {
    test_zone_com = {
      zone_id      = module.test_zone_com.route53_zone_zone_id["test-zone.com"]
      name_servers = module.test_zone_com.route53_zone_name_servers["test-zone.com"]
      records      = module.test_zone_com_records.route53_record_name
    }
    testing_zone_com = {
      zone_id      = module.testing_zone.route53_zone_zone_id["testing-zone.com"]
      name_servers = module.testing_zone.route53_zone_name_servers["testing-zone.com"]
      records      = module.testing_zone_records.route53_record_name
    }
    subdomain_test_zone_com = {
      zone_id      = module.subdomain_zone.route53_zone_zone_id["subdomain.test-zone.com"]
      name_servers = module.subdomain_zone.route53_zone_name_servers["subdomain.test-zone.com"]
      records      = module.subdomain_zone_records.route53_record_name
    }
  }
}