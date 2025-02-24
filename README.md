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
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:DeleteItem"
            ],
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
# Example: my-domain.com.tf
module "my_domain_com" {
  source  = "terraform-aws-modules/route53/aws//modules/zones"
  version = "~> 3.0"

  zones = {
    "my-domain.com" = {
      comment = "My domain managed by Terraform"
      tags    = var.common_tags
    }
  }
}

module "my_domain_com_records" {
  source  = "terraform-aws-modules/route53/aws//modules/records"
  version = "~> 3.0"

  zone_name = "my-domain.com"

  records = [
    {
      name    = ""  # apex record
      type    = "A"
      ttl     = 300
      records = ["192.0.2.1"]
    },
    {
      name    = "www"
      type    = "CNAME"
      ttl     = 300
      records = ["my-domain.com"]
    }
  ]

  depends_on = [module.my_domain_com]
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
# Example: subdomain.my-domain.com.tf
module "subdomain_zone" {
  source  = "terraform-aws-modules/route53/aws//modules/zones"
  version = "~> 3.0"

  zones = {
    "subdomain.my-domain.com" = {
      comment = "Subdomain of my-domain.com"
      tags    = var.common_tags
    }
  }
}

module "subdomain_zone_records" {
  source  = "terraform-aws-modules/route53/aws//modules/records"
  version = "~> 3.0"

  zone_name = "subdomain.my-domain.com"
  
  records = [
    # Subdomain records here
  ]

  depends_on = [module.subdomain_zone]
}

# Add NS records to parent zone
module "delegation_records" {
  source  = "terraform-aws-modules/route53/aws//modules/records"
  version = "~> 3.0"

  zone_name = "my-domain.com"

  records = [
    {
      name    = "subdomain"
      type    = "NS"
      ttl     = 300
      records = module.subdomain_zone.route53_zone_name_servers["subdomain.my-domain.com"]
    }
  ]

  depends_on = [module.my_domain_com, module.subdomain_zone]
}
```

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