# environments/dev/backend.hcl
bucket         = "mym-route53-mgmt-dev-terraform-state"  # Use your actual bucket name
key            = "route53/test-zone/terraform.tfstate"
region         = "eu-west-2"
dynamodb_table = "mym-route53-mgmt-dev-terraform-locks"  # Use your actual DynamoDB table name
encrypt        = true