variable "common_tags" {
  description = "Common tags to be applied to all resources"
  type        = map(string)
}

variable "environment" {
  description = "The environment (e.g., dev, staging, prod)"
  type        = string
}