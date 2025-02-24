# environments/dev/terraform.tfvars
aws_region  = "us-east-1"
environment = "dev"

default_tags = {
  Environment = "dev"
  ManagedBy   = "terraform"
}