# root/outputs.tf

output "zones" {
  description = "All Route53 zone information"
  value = module.zones.all_zones
}

# Optional specific zone outputs if needed
output "test_zone_details" {
  description = "Details for test-zone.com"
  value = module.zones.test_zone_com
}

output "testing_zone_details" {
  description = "Details for testing-zone.com"
  value = module.zones.testing_zone_com
}

output "subdomain_details" {
  description = "Details for subdomain.test-zone.com"
  value = module.zones.subdomain_test_zone_com
}