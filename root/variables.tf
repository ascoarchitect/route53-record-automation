# root/variables.tf
variable "aws_region" {
  description = "AWS region where resources will be created"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
}

variable "default_tags" {
  description = "Default tags to apply to all resources"
  type        = map(string)
  default = {
    ManagedBy = "terraform"
  }
}

variable "zones" {
  description = "Map of Route53 zone configurations"
  type = map(object({
    domain_name        = string
    comment           = optional(string)
    delegation_set_id = optional(string)
    force_destroy     = optional(bool, false)
    vpc = optional(object({
      vpc_id     = string
      vpc_region = optional(string)
    }))
    tags = optional(map(string))
  }))
  default = {}
}

variable "records" {
  description = "Map of DNS record configurations per zone"
  type = map(object({
    zone_name = string
    ttl       = optional(number, 300)
    records = map(object({
      name = string
      type = string
      ttl  = optional(number)
      records = optional(list(string))
      alias = optional(object({
        name                   = string
        zone_id               = string
        evaluate_target_health = optional(bool, false)
      }))
      set_identifier = optional(string)
      health_check_id = optional(string)
      failover_routing_policy = optional(object({
        type = string
      }))
      geolocation_routing_policy = optional(object({
        continent_code   = optional(string)
        country_code    = optional(string)
        subdivision_code = optional(string)
      }))
      latency_routing_policy = optional(object({
        region = string
      }))
      weighted_routing_policy = optional(object({
        weight = number
      }))
      multivalue_answer_routing_policy = optional(bool)
    }))
  }))
  default = {}

  validation {
    condition = alltrue([
      for zone, zone_config in var.records : alltrue([
        for record_name, record in zone_config.records : contains([
          "A", "AAAA", "CAA", "CNAME", "DS", "MX", "NAPTR", "NS", "PTR", 
          "SOA", "SPF", "SRV", "TXT"
        ], record.type)
      ])
    ])
    error_message = "Invalid record type. Allowed values are: A, AAAA, CAA, CNAME, DS, MX, NAPTR, NS, PTR, SOA, SPF, SRV, TXT"
  }
}

variable "enable_health_checks" {
  description = "Whether to enable Route53 health checks"
  type        = bool
  default     = false
}

variable "health_checks" {
  description = "Map of Route53 health check configurations"
  type = map(object({
    fqdn              = string
    port              = number
    type              = string
    resource_path     = optional(string)
    failure_threshold = optional(number)
    request_interval  = optional(number)
    tags             = optional(map(string))
  }))
  default = {}
}