# README.md
# Route53 Zone Management with Terraform

This repository contains Terraform configurations for managing Route53 DNS zones and records centrally using the terraform-aws-modules community modules. The project uses an S3 backend for state storage and DynamoDB for state locking.

## Features

- Uses community-maintained terraform-aws-modules/route53
- Centralized management of multiple Route53 zones
- Support for zone delegation and subdomains
- GitHub Actions pipeline with OIDC authentication
- Environment-specific configurations
- Modular and reusable components

## Prerequisites

- Terraform >= 1.0.0
- AWS CLI configured with appropriate permissions
- GitHub repository with necessary secrets and variables:
  - `AWS_ROLE_ARN`: ARN of the IAM role for OIDC authentication
  - `AWS_REGION`: AWS region for deployment

## Project Structure

- `.github/workflows/`: GitHub Actions workflow configurations
- `backend/`: Terraform configuration for state management infrastructure
- `environments/`: Environment-specific configurations
- `root/`: Main Terraform configurations
  - `zones/`: Individual zone configurations

## Usage

1. Configure GitHub repository:
   - Set up AWS OIDC provider and IAM role
   - Add required secrets and variables
   - Configure environment protection rules if needed

2. Create backend infrastructure:
   ```bash
   cd backend
   terraform init
   terraform apply
   ```

3. Initialize main configuration:
   ```bash
   cd ../root
   terraform init -backend-config=../environments/dev/backend.hcl
   ```

4. All further changes should be made through pull requests:
   - Changes will be automatically planned
   - Plan output will be added as a PR comment
   - Changes will be applied automatically when merged to main

## Adding a New Zone

1. Update the zones configuration in the appropriate environment's tfvars file
2. For subdomains, ensure proper NS record delegation is configured
3. Commit changes and create a pull request

## Module Documentation

For detailed information about the Route53 modules, please refer to:
- [terraform-aws-modules/route53/zones](https://registry.terraform.io/modules/terraform-aws-modules/route53/aws/latest/submodules/zones)
- [terraform-aws-modules/route53/records](https://registry.terraform.io/modules/terraform-aws-modules/route53/aws/latest/submodules/records)

## Security Considerations

- Uses OIDC authentication instead of long-lived credentials
- Environment-specific state files and configurations
- Protected environments for production deployments