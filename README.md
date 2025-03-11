# Route53 Zone Management with Terraform

This repository contains Terraform configurations for managing Route53 DNS zones and records centrally. The project uses an S3 backend for state storage and DynamoDB for state locking.

## Features

- Centralized management of multiple Route53 zones
- Support for zone delegation and subdomains
- GitHub Actions pipeline with OIDC authentication
- Multi-environment support (dev, staging, prod)
- Delegation sets for consistent nameservers
- Role-based authentication

## Prerequisites

- Terraform >= 1.7.0
- AWS Route53 Public Registry Module >= 4.0
- AWS CLI configured with appropriate permissions
- GitHub repository with necessary secrets and variables:
  - `AWS_ROLE_ARN`: ARN of the IAM role for OIDC authentication
  - `AWS_REGION`: AWS region for deployment (e.g., eu-west-2)
  - `TERRAFORM_VERSION`: Version of Terraform to use (e.g., 1.7.x)

## AWS IAM Policy

The following is a policy which is granted to the IAM role for carrying out actions within the scope of this project, using a least-privilege approach:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Statement1",
      "Effect": "Allow",
      "Action": [
        "route53:GetHostedZone",
        "route53:ListHostedZones",
        "route53:ListResourceRecordSets",
        "route53:ChangeResourceRecordSets",
        "route53:CreateHostedZone",
        "route53:DeleteHostedZone",
        "route53:GetChange",
        "route53:ListTagsForResource",
        "route53:ListTagsForResources",
        "route53:ChangeTagsForResource",
        "route53:GetReusableDelegationSet",
        "route53:CreateReusableDelegationSet"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::your-s3-bucket",
        "arn:aws:s3:::your-s3-bucket/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"],
      "Resource": "arn:aws:dynamodb:*:*:table/your-dynamodb-table"
    }
  ]
}
```

## Project Structure

```
.
├── .github
│   └── workflows
│       └── terraform.yml
├── backend
│   ├── main.tf
│   ├── outputs.tf
│   └── variables.tf
├── environments
│   ├── develop
│   │   ├── backend.hcl
│   │   └── terraform.tfvars
│   ├── staging
│   │   ├── backend.hcl
│   │   └── terraform.tfvars
│   └── prod
│       ├── backend.hcl
│       └── terraform.tfvars
└── root
    ├── main.tf
    ├── outputs.tf
    ├── providers.tf
    ├── variables.tf
    └── zones
        ├── example.com.tf
        ├── subdomain.example.com.tf
        └── testing-zone.com.tf
```

## Branching Strategy

### Branch Structure

- `main` - Production environment
- `staging` - Pre-production testing
- `develop` - Development integration
- `feature/*` - Feature branches
- `hotfix/*` - Emergency fixes
- `release/*` - Release preparation

### Environment Mapping

- `main` → Production (`prod`)
- `staging` → Staging (`staging`)
- `develop` → Development (`dev`)

### Branch Flow

```
feature/* → develop → staging → main
hotfix/* → main (and backported to develop)
```

## Setup

### 1. Configure AWS OIDC Provider and IAM Role

Create the necessary AWS resources for OIDC authentication:

```bash
# Deploy the OIDC provider and IAM role
cd backend
terraform init
terraform apply
```

### 2. Configure GitHub Repository

1. Add repository secrets:

   - `AWS_ROLE_ARN`: The ARN of the IAM role created for OIDC authentication

2. Add repository variables:

   - `AWS_REGION`: AWS region (e.g., eu-west-2)
   - `TERRAFORM_VERSION`: Version of Terraform to use (e.g., 1.7.x)

3. Configure environments in GitHub:
   - Create environments: `dev`, `staging`, `prod`
   - Add appropriate protection rules for each environment

### 3. Initialize Backend Infrastructure

```bash
cd backend
terraform init
terraform apply -var="project_name=route53-mgmt" -var="environment=dev"
```

Repeat for staging and prod environments if needed.

## Usage

### Adding a New Zone

1. Create a feature branch:

```bash
git checkout develop
git pull
git checkout -b feature/add-new-zone
```

2. Create a new zone file in `root/zones/`:

```bash
# Example: root/zones/test-zone.com.tf

# Create the zone
module "test_zone_com" {
  source  = "terraform-aws-modules/route53/aws//modules/zones"
  version = "~> 4.0"
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
  version = "~> 4.0"

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
```

3. Commit and push your changes:

```bash
git add .
git commit -m "feat: add my-domain.com zone"
git push origin feature/add-new-zone
```

4. Create a pull request to the `develop` branch

   - GitHub Actions will run the Terraform plan
   - Review the plan in the PR comments

5. After PR approval and merge:
   - Changes will be applied to the dev environment
   - Promote to staging and prod via PR to those branches

### Adding a Subdomain with Delegation

1. Create a new file for the subdomain:

```bash
# Example: root/zones/subdomain.test-zone.com.tf

# Create delegation set
module "subdomain_test-zone_com_delegation_set" {
  source  = "terraform-aws-modules/route53/aws//modules/delegation-sets"
  version = "~> 4.0"

  delegation_sets = {
    "subdomain_set" = {
      reference_name = "subdomain.test-zone.com"
    }
  }
}

# Create the subdomain zone using the delegation set
module "subdomain_test-zone_com_subdomain_zone" {
  source  = "terraform-aws-modules/route53/aws//modules/zones"
  version = "~> 4.0"

  zones = {
    "subdomain.test-zone.com" = {
      comment           = "Subdomain of test-zone.com managed by Terraform"
      delegation_set_id = module.subdomain_test-zone_com_delegation_set.route53_delegation_set_id["subdomain_set"]
      tags              = var.common_tags
    }
  }

  depends_on = [module.subdomain_test-zone_com_delegation_set]
}

# Configure the records for the subdomain
module "subdomain_test-zone_com_subdomain_zone_records" {
  source  = "terraform-aws-modules/route53/aws//modules/records"
  version = "~> 4.0"

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

  depends_on = [module.subdomain_test-zone_com_subdomain_zone]
}

# Add NS records to the parent zone for delegation
module "subdomain_test-zone_com_delegation_records" {
  source  = "terraform-aws-modules/route53/aws//modules/records"
  version = "~> 4.0"

  zone_name = "test-zone.com"

  records = [
    {
      name    = "subdomain"
      type    = "NS"
      ttl     = 300
      records = module.subdomain_test-zone_com_subdomain_zone.route53_zone_name_servers["subdomain.test-zone.com"]
    }
  ]

  depends_on = [module.test_zone_com, module.subdomain_test-zone_com_subdomain_zone]
}
```

## Updating Outputs

When creating a new domain or subdomain, you need to update the `outputs.tf` file to include the new resources. This ensures that the necessary outputs are available for other modules or for reference.

### Example: Adding Outputs for a New Domain

1. Open the `outputs.tf` file located in the `root` directory.

2. Add the following outputs for the new domain:

```bash
# Example zone: test-zone.com
# filepath: ./root/outputs.tf

output "test_zone_com_zone_id" {
  description = "The ID of the test-zone.com hosted zone"
  value       = module.test_zone_com.route53_zone_id["test-zone.com"]
}

output "test_zone_com_name_servers" {
  description = "The name servers of the test-zone.com hosted zone"
  value       = module.test_zone_com.route53_zone_name_servers["test-zone.com"]
```

### Example: Adding Outputs for a New Subdomain

1. Open the outputs.tf file located in the root directory.

2. Add the following outputs for the new subdomain:

```bash
# Example zone: subdomain.test-zone.com
# filepath: ./root/outputs.tf

output "subdomain_test_zone_com_zone_id" {
  description = "The ID of the subdomain.test-zone.com hosted zone"
  value       = module.subdomain_test_zone_com_subdomain_zone.route53_zone_id["subdomain.test-zone.com"]
}

output "subdomain_test_zone_com_name_servers" {
  description = "The name servers of the subdomain.test-zone.com hosted zone"
  value       = module.subdomain_test_zone_com_subdomain_zone.route53_zone_name_servers["subdomain.test-zone.com"]
}
```

By updating the outputs.tf file, you ensure that the new domain or subdomain resources are properly exposed and can be referenced in other parts of your Terraform configuration.

## Local Development

For local testing and development:

```bash
cd root
terraform init -backend-config="../environments/dev/backend.hcl"
terraform plan -var-file="../environments/dev/terraform.tfvars"
```

## CI/CD Pipeline

The GitHub Actions workflow will:

1. Run on push to main, staging, develop branches
2. Run on pull requests to these branches
3. Use OIDC for secure AWS authentication
4. Execute format checks and validation
5. Generate a plan for review
6. Apply changes when merged to target branches

Key improvements in the workflow:

1. Multi-environment support (dev, staging, prod)
2. Concurrency control to prevent parallel deployments
3. Branch-based environment selection
4. Use of plan files for consistent apply
5. PR comments with detailed plan output

## Security Considerations

- Uses OIDC authentication instead of long-lived credentials
- Environment-specific state files and configurations
- Protected environments for production deployments
- Concurrency controls to prevent race conditions
- Least privilege IAM permissions

## Troubleshooting

If you encounter issues:

1. Verify AWS credentials and permissions
2. Check GitHub secrets and variables
3. Ensure the correct environment variables are set
4. Review the GitHub Actions workflow logs
5. Verify your local Terraform state is in sync

## Contributing

1. Create a feature branch from develop
2. Make your changes
3. Create a PR to develop
4. After approval and testing, changes can be promoted to staging and then production

## License

This project is licensed under the Apache 2.0 License - see the LICENSE file for details.
