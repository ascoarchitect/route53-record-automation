#!/usr/bin/env python3
"""
Route53 Terraform Zone File Generator

This script connects to AWS Route53 and generates Terraform configuration files
for existing hosted zones that haven't been imported yet.

The script automatically detects its location and finds the correct project
structure. It expects to be placed in <project_root>/scripts/ and will create
zone files in <project_root>/root/zones/

Usage:
    python generate_terraform_zones.py --domain example.com  # Process single domain
    python generate_terraform_zones.py --all-domains        # Process all domains
    python generate_terraform_zones.py --dry-run           # Show what would be created
    python generate_terraform_zones.py --force             # Overwrite existing files
    python generate_terraform_zones.py --import-blocks    # Generate import blocks for existing zones
    
The script can be run from any directory - it will automatically find the correct paths.
"""

import os
import sys
import argparse
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Configuration
# Get the script's directory and calculate the zones directory path
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent  # Go up one level from scripts/ to project root
ZONES_DIR = PROJECT_ROOT / "root" / "zones"
ROOT_DIR = PROJECT_ROOT / "root"
TERRAFORM_MODULE_VERSION = "~> 5.0"


class Route53TerraformGenerator:
    """Generate Terraform configuration files for Route53 zones."""
    
    def __init__(self, zones_dir: str = None, dry_run: bool = False, force: bool = False, import_blocks: bool = False):
        """Initialize the generator with AWS client and configuration."""
        # Use provided zones_dir or default to calculated path
        if zones_dir:
            self.zones_dir = Path(zones_dir)
            self.root_dir = self.zones_dir.parent
        else:
            self.zones_dir = ZONES_DIR
            self.root_dir = ROOT_DIR

        self.dry_run = dry_run
        self.force = force
        self.import_blocks = import_blocks
        self.processed_zones = []  # Track zones that were processed for outputs
        
        # Print the directory being used for clarity
        print(f"Using zones directory: {self.zones_dir.absolute()}")
        print(f"Using root directory: {self.root_dir.absolute()}")
        
        try:
            self.route53 = boto3.client('route53')
            # Test connection
            self.route53.list_hosted_zones(MaxItems='1')
        except NoCredentialsError:
            print("Error: AWS credentials not found. Please configure your AWS credentials.")
            sys.exit(1)
        except ClientError as e:
            print(f"Error connecting to AWS Route53: {e}")
            sys.exit(1)
            
        # Ensure zones directory exists
        if not self.dry_run:
            if not self.zones_dir.parent.exists():
                print(f"Error: Parent directory {self.zones_dir.parent.absolute()} does not exist.")
                print("Expected project structure:")
                print("  project_root/")
                print("    ├── scripts/           <- This script should be here")
                print("    │   └── generate_terraform_zones.py")
                print("    └── root/")
                print("        ├── outputs.tf    <- Will be updated")
                print("        └── zones/        <- Zone files will be created here")
                print("            └── outputs.tf <- Will be updated")
                print("\nMake sure the script is in the correct location.")
                sys.exit(1)
            self.zones_dir.mkdir(parents=True, exist_ok=True)
    
    def sanitize_module_name(self, domain: str) -> str:
        """Convert domain name to valid Terraform module name."""
        # Replace dots and hyphens with underscores, ensure valid start char
        name = domain.replace('.', '_').replace('-', '_')
        # Terraform identifiers must start with a letter or underscore
        if not name or not (name[0].isalpha() or name[0] == '_'):
            name = f"_{name}"
        # Keep only letters, digits, and underscores
        sanitized = []
        for ch in name:
            if ch.isalnum() or ch == '_':
                sanitized.append(ch)
            else:
                sanitized.append('_')
        return ''.join(sanitized)
    
    def get_terraform_filename(self, domain: str) -> str:
        """Generate the Terraform filename for a domain."""
        return f"{domain}.tf"
    
    def check_file_exists(self, domain: str) -> bool:
        """Check if Terraform file already exists for the domain."""
        file_path = self.zones_dir / self.get_terraform_filename(domain)
        return file_path.exists()
    
    def parse_zones_outputs_file(self) -> Tuple[Set[str], Dict[str, Any]]:
        """Parse the zones/outputs.tf file and return existing zones and structure."""
        outputs_file = self.zones_dir / "outputs.tf"
        existing_zones = set()
        all_zones_content = {}
        
        if outputs_file.exists():
            with open(outputs_file, 'r') as f:
                content = f.read()
                
                # Find individual zone output blocks
                output_pattern = r'output\s+"([^"]+)"'
                matches = re.findall(output_pattern, content)
                for match in matches:
                    if match != "all_zones":  # Skip the combined output
                        existing_zones.add(match)
                
                # Try to parse the all_zones output structure
                all_zones_pattern = r'output\s+"all_zones"\s*{[^}]*value\s*=\s*{([^}]*)}'
                all_zones_match = re.search(all_zones_pattern, content, re.DOTALL)
                if all_zones_match:
                    # Extract zone entries from all_zones
                    zone_entry_pattern = r'(\w+)\s*=\s*{'
                    zone_entries = re.findall(zone_entry_pattern, all_zones_match.group(1))
                    for zone_entry in zone_entries:
                        all_zones_content[zone_entry] = True
        
        return existing_zones, all_zones_content
    
    def parse_root_outputs_file(self) -> Set[str]:
        """Parse the root/outputs.tf file and return existing zone references."""
        outputs_file = self.root_dir / "outputs.tf"
        existing_outputs = set()
        
        if outputs_file.exists():
            with open(outputs_file, 'r') as f:
                content = f.read()
                
                # Find output blocks
                output_pattern = r'output\s+"([^"]+)"'
                matches = re.findall(output_pattern, content)
                existing_outputs.update(matches)
        
        return existing_outputs
    
    def generate_zone_output_block(self, zone_name: str, module_name: str, is_subdomain: bool = False, has_records: bool = True) -> List[str]:
        """Generate a single zone output block for zones/outputs.tf."""
        lines = []
        output_name = self.sanitize_module_name(zone_name)
        
        # Determine module references based on whether it's a subdomain
        if is_subdomain:
            zone_module = f"{module_name}_subdomain_zone"
            records_module = f"{module_name}_subdomain_zone_records"
        else:
            zone_module = module_name
            records_module = f"{module_name}_records"
        
        lines.append(f'# Output {zone_name} details')
        lines.append(f'output "{output_name}" {{')
        lines.append(f'  description = "Details for {zone_name}"')
        lines.append(f'  value = {{')
        lines.append(f'    zone_id      = module.{zone_module}.route53_zone_zone_id["{zone_name}"]')
        lines.append(f'    name_servers = module.{zone_module}.route53_zone_name_servers["{zone_name}"]')
        if has_records:
            lines.append(f'    records      = module.{records_module}.route53_record_name')
        else:
            lines.append(f'    records      = {{}}')
        lines.append(f'  }}')
        lines.append(f'}}')
        
        return lines
    
    def update_zones_outputs_file(self) -> None:
        """Update the root/zones/outputs.tf file with new zone outputs."""
        if not self.processed_zones:
            return
            
        outputs_file = self.zones_dir / "outputs.tf"
        
        # Parse existing outputs
        existing_zones, all_zones_content = self.parse_zones_outputs_file()
        
        # Determine which zones need to be added
        zones_to_add = []
        for zone_info in self.processed_zones:
            output_name = self.sanitize_module_name(zone_info['name'])
            if output_name not in existing_zones:
                zones_to_add.append(zone_info)
        
        if not zones_to_add:
            print("ℹ All zone outputs already exist in zones/outputs.tf")
            return
        
        # Generate new output blocks
        new_output_blocks = []
        all_zones_additions = []
        
        for zone_info in zones_to_add:
            zone_name = zone_info['name']
            module_name = self.sanitize_module_name(zone_name)
            is_subdomain = zone_info.get('is_subdomain', False)
            
            # Generate individual output block
            has_records = zone_info.get('has_records', True)
            output_block = self.generate_zone_output_block(zone_name, module_name, is_subdomain, has_records)
            new_output_blocks.extend(output_block)
            new_output_blocks.append('')  # Add empty line between outputs
            
            # Generate all_zones entry
            if is_subdomain:
                zone_module = f"{module_name}_subdomain_zone"
                records_module = f"{module_name}_subdomain_zone_records"
            else:
                zone_module = module_name
                records_module = f"{module_name}_records"
            
            if zone_info.get('has_records', True):
                all_zones_entry = [
                    f'    {module_name} = {{',
                    f'      zone_id      = module.{zone_module}.route53_zone_zone_id["{zone_name}"]',
                    f'      name_servers = module.{zone_module}.route53_zone_name_servers["{zone_name}"]',
                    f'      records      = module.{records_module}.route53_record_name',
                    f'    }}'
                ]
            else:
                all_zones_entry = [
                    f'    {module_name} = {{',
                    f'      zone_id      = module.{zone_module}.route53_zone_zone_id["{zone_name}"]',
                    f'      name_servers = module.{zone_module}.route53_zone_name_servers["{zone_name}"]',
                    f'      records      = {{}}',
                    f'    }}'
                ]
            all_zones_additions.append('\n'.join(all_zones_entry))
        
        if self.dry_run:
            print(f"\n[DRY RUN] Would update: {outputs_file}")
            print(f"[DRY RUN] Would add {len(zones_to_add)} new zone output(s):")
            for zone in zones_to_add:
                print(f"  - {zone['name']}")
            print("\n[DRY RUN] Individual output preview:")
            for line in new_output_blocks[:15]:
                print(f"  {line}")
            if len(new_output_blocks) > 15:
                print(f"  ... ({len(new_output_blocks) - 15} more lines)")
        else:
            # Read existing content
            existing_content = ""
            if outputs_file.exists():
                with open(outputs_file, 'r') as f:
                    existing_content = f.read()
            
            # If file doesn't exist, create with full structure
            if not existing_content:
                content = self._generate_full_zones_outputs_file(zones_to_add)
            else:
                # Add new individual outputs before the all_zones output
                # Find the position of "output "all_zones""
                all_zones_pos = existing_content.find('output "all_zones"')
                
                if all_zones_pos > 0:
                    # Insert new outputs before all_zones
                    before_all_zones = existing_content[:all_zones_pos].rstrip()
                    all_zones_section = existing_content[all_zones_pos:]
                    
                    # Add new individual outputs
                    new_outputs = '\n\n' + '\n'.join(new_output_blocks).rstrip() + '\n\n'
                    
                    # Update all_zones section
                    # Find the closing brace of the value block
                    value_end = all_zones_section.rfind('  }')
                    if value_end > 0:
                        # Insert new zones into all_zones
                        for entry in all_zones_additions:
                            insertion_point = value_end
                            all_zones_section = (
                                all_zones_section[:insertion_point] +
                                entry + '\n' +
                                all_zones_section[insertion_point:]
                            )
                    
                    content = before_all_zones + new_outputs + all_zones_section
                else:
                    # No all_zones found, append everything
                    content = existing_content.rstrip() + '\n\n' + self._generate_full_zones_outputs_file(zones_to_add)
            
            # Write updated content
            with open(outputs_file, 'w') as f:
                f.write(content)
            
            print(f"✓ Updated zones/outputs.tf with {len(zones_to_add)} new zone output(s)")
            for zone in zones_to_add:
                print(f"  + {zone['name']}")
    
    def _generate_full_zones_outputs_file(self, zones: List[Dict[str, Any]]) -> str:
        """Generate a complete zones/outputs.tf file structure."""
        lines = []
        all_zones_entries = []
        
        # Generate individual outputs
        for zone_info in zones:
            zone_name = zone_info['name']
            module_name = self.sanitize_module_name(zone_name)
            is_subdomain = zone_info.get('is_subdomain', False)
            
            has_records = zone_info.get('has_records', True)
            output_block = self.generate_zone_output_block(zone_name, module_name, is_subdomain, has_records)
            lines.extend(output_block)
            lines.append('')
            
            # Prepare all_zones entry
            if is_subdomain:
                zone_module = f"{module_name}_subdomain_zone"
                records_module = f"{module_name}_subdomain_zone_records"
            else:
                zone_module = module_name
                records_module = f"{module_name}_records"
            
            if zone_info.get('has_records', True):
                all_zones_entry = [
                    f'    {module_name} = {{',
                    f'      zone_id      = module.{zone_module}.route53_zone_zone_id["{zone_name}"]',
                    f'      name_servers = module.{zone_module}.route53_zone_name_servers["{zone_name}"]',
                    f'      records      = module.{records_module}.route53_record_name',
                    f'    }}'
                ]
            else:
                all_zones_entry = [
                    f'    {module_name} = {{',
                    f'      zone_id      = module.{zone_module}.route53_zone_zone_id["{zone_name}"]',
                    f'      name_servers = module.{zone_module}.route53_zone_name_servers["{zone_name}"]',
                    f'      records      = {{}}',
                    f'    }}'
                ]
            all_zones_entries.append('\n'.join(all_zones_entry))
        
        # Add combined output
        lines.append('# Combined output of all zones')
        lines.append('output "all_zones" {')
        lines.append('  description = "Combined information for all zones"')
        lines.append('  value = {')
        lines.append('\n'.join(all_zones_entries))
        lines.append('  }')
        lines.append('}')
        
        return '\n'.join(lines)
    
    def update_root_outputs_file(self) -> None:
        """Update the root/outputs.tf file with references to zone outputs."""
        if not self.processed_zones:
            return
            
        outputs_file = self.root_dir / "outputs.tf"
        existing_outputs = self.parse_root_outputs_file()
        
        # Generate new output references
        zones_to_add = []
        for zone_info in self.processed_zones:
            zone_name = zone_info['name']
            module_name = self.sanitize_module_name(zone_name)
            output_name = f"{module_name}_details"
            
            if output_name not in existing_outputs:
                zones_to_add.append(zone_info)
        
        if not zones_to_add:
            print("ℹ All zone references already exist in root/outputs.tf")
            return
        
        # Generate new output blocks
        new_outputs = []
        for zone_info in zones_to_add:
            zone_name = zone_info['name']
            module_name = self.sanitize_module_name(zone_name)
            
            new_outputs.append(f'output "{module_name}_details" {{')
            new_outputs.append(f'  description = "Details for {zone_name}"')
            new_outputs.append(f'  value = module.zones.{module_name}')
            new_outputs.append('}')
            new_outputs.append('')
        
        if self.dry_run:
            print(f"\n[DRY RUN] Would update: {outputs_file}")
            print(f"[DRY RUN] Would add {len(zones_to_add)} new zone reference(s):")
            for zone in zones_to_add:
                print(f"  - {zone['name']}")
        else:
            # Read existing content
            existing_content = ""
            if outputs_file.exists():
                with open(outputs_file, 'r') as f:
                    existing_content = f.read()
            else:
                # Create basic structure if file doesn't exist
                existing_content = '''output "zones" {
  description = "All Route53 zone information"
  value = module.zones.all_zones
}

'''
            
            # Append new outputs
            new_content = existing_content.rstrip() + '\n\n' + '\n'.join(new_outputs)
            
            # Write updated content
            with open(outputs_file, 'w') as f:
                f.write(new_content)
            
            print(f"✓ Updated root/outputs.tf with {len(zones_to_add)} new zone reference(s)")
            for zone in zones_to_add:
                print(f"  + {zone['name']}")
    
    def list_hosted_zones(self) -> List[Dict[str, Any]]:
        """List all hosted zones from Route53."""
        zones = []
        paginator = self.route53.get_paginator('list_hosted_zones')
        
        try:
            for page in paginator.paginate():
                for zone in page['HostedZones']:
                    # Remove trailing dot from zone name
                    zone_name = zone['Name'].rstrip('.')
                    zones.append({
                        'id': zone['Id'].replace('/hostedzone/', ''),
                        'name': zone_name,
                        'private': zone.get('Config', {}).get('PrivateZone', False),
                        'comment': zone.get('Config', {}).get('Comment', ''),
                        'resource_record_set_count': zone.get('ResourceRecordSetCount', 0)
                    })
        except ClientError as e:
            print(f"Error listing hosted zones: {e}")
            sys.exit(1)
            
        return zones
    
    def get_zone_records(self, zone_id: str, zone_name: str) -> List[Dict[str, Any]]:
        """Get all records for a specific zone."""
        records = []
        paginator = self.route53.get_paginator('list_resource_record_sets')
        
        try:
            for page in paginator.paginate(HostedZoneId=zone_id):
                for record_set in page['ResourceRecordSets']:
                    # Skip NS and SOA records for the apex domain as they're managed by AWS
                    if record_set['Type'] in ['NS', 'SOA'] and record_set['Name'].rstrip('.') == zone_name:
                        continue
                        
                    record_data = {
                        'name': record_set['Name'].rstrip('.'),
                        'type': record_set['Type'],
                        'ttl': record_set.get('TTL'),
                        'records': []
                    }
                    
                    # Handle standard records
                    if 'ResourceRecords' in record_set:
                        record_data['records'] = [r['Value'] for r in record_set['ResourceRecords']]
                    
                    # Handle alias records
                    if 'AliasTarget' in record_set:
                        record_data['alias'] = {
                            'name': record_set['AliasTarget']['DNSName'].rstrip('.'),
                            'zone_id': record_set['AliasTarget']['HostedZoneId'],
                            'evaluate_target_health': record_set['AliasTarget']['EvaluateTargetHealth']
                        }
                        record_data['ttl'] = None  # Alias records don't have TTL
                    
                    records.append(record_data)
                    
        except ClientError as e:
            print(f"Error listing records for zone {zone_name}: {e}")
            
        return records
    
    def is_subdomain(self, domain: str, zones: List[Dict[str, Any]]) -> Optional[str]:
        """Check if domain is a subdomain of any existing zone."""
        for zone in zones:
            if domain != zone['name'] and domain.endswith('.' + zone['name']):
                return zone['name']
        return None
    
    def generate_terraform_content(self, zone: Dict[str, Any], records: List[Dict[str, Any]], 
                                  parent_zone: Optional[str] = None) -> str:
        """Generate Terraform configuration content for a zone."""
        zone_name = zone['name']
        module_name = self.sanitize_module_name(zone_name)
        
        content = []
        content.append(f"# Terraform configuration for {zone_name}")
        content.append(f"# Generated automatically - review before applying")
        content.append("")
        
        # For subdomains, create delegation set first
        if parent_zone:
            content.append(f"# Create delegation set for subdomain")
            content.append(f'module "{module_name}_delegation_set" {{')
            content.append(f'  source  = "terraform-aws-modules/route53/aws//modules/delegation-sets"')
            content.append(f'  version = "{TERRAFORM_MODULE_VERSION}"')
            content.append("")
            content.append("  delegation_sets = {")
            content.append(f'    "{module_name}_set" = {{')
            content.append(f'      reference_name = "{zone_name}"')
            content.append("    }")
            content.append("  }")
            content.append("}")
            content.append("")
        
        # Create the zone
        content.append(f"# Create the {'subdomain ' if parent_zone else ''}zone")
        content.append(f'module "{module_name}{"_subdomain_zone" if parent_zone else ""}" {{')
        content.append(f'  source  = "terraform-aws-modules/route53/aws//modules/zones"')
        content.append(f'  version = "{TERRAFORM_MODULE_VERSION}"')
        content.append("")
        content.append("  zones = {")
        content.append(f'    "{zone_name}" = {{')
        
        if zone['comment']:
            content.append(f'      comment = "{zone["comment"]}"')
        else:
            content.append(f'      comment = "{zone_name} managed by Terraform"')
        
        if parent_zone:
            content.append(f'      delegation_set_id = module.{module_name}_delegation_set.route53_delegation_set_id["{module_name}_set"]')
        
        content.append("      tags = merge(")
        content.append("        var.common_tags,")
        content.append("        {")
        content.append('          Environment = var.environment')
        content.append(f'          Zone        = "{zone_name}"')
        content.append("        }")
        content.append("      )")
        content.append("    }")
        content.append("  }")
        
        if parent_zone:
            content.append("")
            content.append(f'  depends_on = [module.{module_name}_delegation_set]')
        
        content.append("}")
        content.append("")

        # Create records module only if there are records (excluding NS/SOA)
        if records:
            content.append("# Create zone records")
            content.append(f'module "{module_name}{"_subdomain_zone" if parent_zone else ""}_records" {{')
            content.append(f'  source  = "terraform-aws-modules/route53/aws//modules/records"')
            content.append(f'  version = "{TERRAFORM_MODULE_VERSION}"')
            content.append("")
            # Prefer zone_name to avoid unknown values at plan time that can force replacement
            content.append(f'  zone_name = "{zone_name}"')
            content.append("")
            content.append("  records = [")

            for record in records:
                # Calculate the relative name for the record
                if record['name'] == zone_name:
                    record_name = ''
                elif record['name'].endswith('.' + zone_name):
                    record_name = record['name'][:-len(zone_name)-1]
                else:
                    record_name = record['name']

                # Normalize apex label encodings and suffixes
                if record_name:
                    record_name = record_name.replace('\\100', '@')
                    if record_name == '@':
                        record_name = ''
                    elif record_name.endswith('.@') or record_name.endswith('.\\100'):
                        record_name = record_name.rsplit('.', 1)[0]

                content.append("    {")
                content.append(f'      name = "{record_name}"')
                content.append(f'      type = "{record["type"]}"')

                if 'alias' in record:
                    content.append("      alias = {")
                    content.append(f'        name    = "{record["alias"]["name"]}"')
                    content.append(f'        zone_id = "{record["alias"]["zone_id"]}"')
                    content.append(f'        evaluate_target_health = {str(record["alias"]["evaluate_target_health"]).lower()}')
                    content.append("      }")
                else:
                    if record['ttl']:
                        content.append(f'      ttl  = {record["ttl"]}')

                    if record['records']:
                        if record['type'] == 'TXT':
                            # TXT records: pass literal content without adding extra quotes
                            formatted_records = []
                            for r in record['records']:
                                # Remove outer quotes if present (console may show quoted)
                                if r.startswith('"') and r.endswith('"'):
                                    r = r[1:-1]
                                # Escape for HCL string literal only
                                r = r.replace('\\', '\\\\').replace('"', '\\"')
                                formatted_records.append(f'"{r}"')
                        elif record['type'] == 'MX':
                            # MX records are already formatted with priority
                            formatted_records = [f'"{r}"' for r in record['records']]
                        else:
                            formatted_records = [f'"{r}"' for r in record['records']]

                        if len(formatted_records) == 1:
                            content.append(f'      records = [{formatted_records[0]}]')
                        else:
                            content.append("      records = [")
                            for r in formatted_records:
                                content.append(f"        {r},")
                            content.append("      ]")

                content.append("    },")

            content.append("  ]")
            content.append("")
            content.append("}")
            content.append("")
        
        # For subdomains, add NS delegation records to parent zone
        if parent_zone:
            parent_module_name = self.sanitize_module_name(parent_zone)
            subdomain_prefix = zone_name[:-len(parent_zone)-1]
            
            content.append("# Add NS records to the parent zone for delegation")
            content.append(f'module "{module_name}_delegation_records" {{')
            content.append(f'  source  = "terraform-aws-modules/route53/aws//modules/records"')
            content.append(f'  version = "{TERRAFORM_MODULE_VERSION}"')
            content.append("")
            content.append(f'  zone_name = "{parent_zone}"')
            content.append("")
            content.append("  records = [")
            content.append("    {")
            content.append(f'      name = "{subdomain_prefix}"')
            content.append('      type = "NS"')
            content.append('      ttl  = 300')
            content.append(f'      records = module.{module_name}_subdomain_zone.route53_zone_name_servers["{zone_name}"]')
            content.append("    }")
            content.append("  ]")
            content.append("")
            content.append("}")
        
        return "\n".join(content)
    
    def write_terraform_file(self, domain: str, content: str) -> None:
        """Write Terraform configuration to file."""
        file_path = self.zones_dir / self.get_terraform_filename(domain)
        
        if self.dry_run:
            print(f"[DRY RUN] Would create file: {file_path}")
            print(f"[DRY RUN] Content preview (first 20 lines):")
            lines = content.split('\n')[:20]
            for line in lines:
                print(f"  {line}")
            if len(content.split('\n')) > 20:
                print(f"  ... ({len(content.split('\n')) - 20} more lines)")
        else:
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"✓ Created: {file_path}")
    
    def process_zone(self, zone: Dict[str, Any], all_zones: List[Dict[str, Any]]) -> bool:
        """Process a single zone and generate its Terraform file."""
        zone_name = zone['name']
        
        # Check if file already exists
        if self.check_file_exists(zone_name) and not self.force:
            print(f"⊘ Skipping {zone_name} - Terraform file already exists (use --force to overwrite)")
            return False
        elif self.check_file_exists(zone_name) and self.force:
            print(f"⚠ Overwriting existing file for {zone_name}")
        
        # Skip private zones (optional - remove this if you want to include private zones)
        if zone['private']:
            print(f"⊘ Skipping {zone_name} - Private zone")
            return False
        
        print(f"→ Processing zone: {zone_name}")

        # Get records for the zone
        records = self.get_zone_records(zone['id'], zone_name)
        print(f"  Found {len(records)} records")
        
        # Check if this is a subdomain
        parent_zone = self.is_subdomain(zone_name, all_zones)
        if parent_zone:
            print(f"  Detected as subdomain of {parent_zone}")
        
        # Generate Terraform content
        content = self.generate_terraform_content(zone, records, parent_zone)
        
        # Write to file
        self.write_terraform_file(zone_name, content)
        
        # Track processed zone for outputs
        self.processed_zones.append({
            'name': zone_name,
            'id': zone['id'],
            'is_subdomain': parent_zone is not None,
            'has_records': len(records) > 0,
            'existing': True,
        })
        
        return True
    
    def generate_verification_commands(self) -> None:
        """Generate commands to verify the correct Terraform resource addresses."""
        if not self.processed_zones:
            return
            
        print("\n" + "="*50)
        print("Verification Commands:")
        print("="*50)
        print("\nBefore importing, run these commands to see the exact resource addresses:\n")
        
        print("1. First, run terraform plan to see what resources will be created:")
        print("   cd root && terraform plan")
        print("\n2. Check the exact resource addresses with:")
        print("   terraform show -json terraform.plan | jq '.planned_values.root_module'")
        print("\n3. Or list all resources that would be created:")
        print("   terraform plan -out=plan.out")
        print("   terraform show -json plan.out | jq -r '.planned_values.root_module.child_modules[].resources[].address'")
        
        print("\nThis will show you the exact resource addresses to use in import commands.")

    def generate_import_commands(self) -> None:
        """Generate terraform import commands for processed zones."""
        if not self.processed_zones:
            return
            
        print("\n" + "="*50)
        print("Terraform Import Commands:")
        print("="*50)
        print("\nRun these commands from the 'root' directory after reviewing the generated files:\n")
        
        print("1. First initialize Terraform:")
        print("   terraform init")
        print("\n2. Import the zones:")
        
        for zone_info in self.processed_zones:
            if not zone_info.get('existing', False):
                continue
            zone_name = zone_info['name']
            zone_id = zone_info['id']
            module_name = self.sanitize_module_name(zone_name)
            
            if zone_info['is_subdomain']:
                # Subdomain zone import
                print(f'   terraform import \'module.zones.module.{module_name}_subdomain_zone.aws_route53_zone.this["{zone_name}"]\' {zone_id}')
            else:
                # Regular zone import
                print(f'   terraform import \'module.zones.module.{module_name}.aws_route53_zone.this["{zone_name}"]\' {zone_id}')
        
        print("\n3. Import the DNS records:")
        
        # Generate import commands for records
        for zone_info in self.processed_zones:
            if not zone_info.get('existing', False):
                continue
            zone_name = zone_info['name']
            zone_id = zone_info['id']
            module_name = self.sanitize_module_name(zone_name)
            
            print(f"\n   # Records for {zone_name}")
            
            # Get records for this zone to generate import commands
            records = self.get_zone_records(zone_id, zone_name)
            
            if zone_info['is_subdomain']:
                records_module = f"{module_name}_subdomain_zone_records"
            else:
                records_module = f"{module_name}_records"
            
            for record in records:
                # Skip records that are typically not imported or managed by Terraform
                if record['type'] in ['NS', 'SOA']:
                    continue
                
                # Calculate the relative name for the record
                if record['name'] == zone_name:
                    record_name = ''  # Apex record
                elif record['name'].endswith('.' + zone_name):
                    record_name = record['name'][:-len(zone_name)-1]
                else:
                    record_name = record['name']
                
                # Normalize apex label encodings and suffixes
                if record_name:
                    record_name = record_name.replace('\\100', '@')
                    if record_name == '@':
                        record_name = ''
                    elif record_name.endswith('.@') or record_name.endswith('.\\100'):
                        record_name = record_name.rsplit('.', 1)[0]

                # Create the Terraform resource key (matches terraform-aws-modules format)
                # Format: "{record_name} {record_type}" where record_name is "" for apex records
                terraform_key = f"{record_name} {record['type']}"
                
                # Create the Route53 record identifier for import (zone_id_name_type format)
                # For apex records, the name in the identifier should be the full zone name
                if record_name == '':
                    import_name = zone_name
                else:
                    import_name = f"{record_name}.{zone_name}"
                
                import_identifier = f"{zone_id}_{import_name}_{record['type']}"
                
                print(f'   terraform import \'module.zones.module.{records_module}.aws_route53_record.this["{terraform_key}"]\' {import_identifier}')
        
        print("\n4. After importing, run terraform plan to see what changes are needed:")
        print("   terraform plan")
        print("\n5. If everything looks good, apply the configuration:")
        print("   terraform apply")
        
        print("\nNotes:")
        print("- The record import format follows terraform-aws-modules/route53 conventions:")
        print("  * Terraform keys: '{record_name} {record_type}' (empty name for apex records)")
        print("  * Import identifiers: 'zone_id_full_record_name_record_type'")
        print("- NS and SOA records are typically skipped as they're managed by AWS")
        print("- You may need to escape quotes differently depending on your shell")
        print("- Some records might fail to import if they have special characters - review manually")
        print("- Use the verification commands above to check exact resource addresses")
    
    def _parse_existing_imports_to_addresses(self, content: str) -> Set[str]:
        """Parse existing imports.tf content to collect existing 'to' addresses."""
        addresses = set()
        # Match lines like: to = module.zones.module.name.aws_...
        for line in content.splitlines():
            line = line.strip()
            if line.startswith('to') and '=' in line:
                # Extract right-hand side
                rhs = line.split('=', 1)[1].strip().strip('"')
                addresses.add(rhs)
        return addresses

    def generate_import_blocks(self) -> None:
        """Generate a root-level imports.tf file with import blocks for zones and records."""
        if not self.processed_zones:
            return

        imports_file = self.root_dir / "imports.tf"

        # Build blocks for zones and their records
        blocks: List[str] = []

        for zone_info in self.processed_zones:
            if not zone_info.get('existing', False):
                continue
            zone_name = zone_info['name']
            zone_id = zone_info['id']
            module_name = self.sanitize_module_name(zone_name)

            if zone_info['is_subdomain']:
                zone_module = f"{module_name}_subdomain_zone"
                records_module = f"{module_name}_subdomain_zone_records"
            else:
                zone_module = module_name
                records_module = f"{module_name}_records"

            # Zone import block
            to_addr_zone = f"module.zones.module.{zone_module}.aws_route53_zone.this[\"{zone_name}\"]"
            blocks.extend([
                "# Import hosted zone",
                "import {",
                f"  to = {to_addr_zone}",
                f"  id = \"{zone_id}\"",
                "}",
                "",
            ])

            # Records for this zone
            records = self.get_zone_records(zone_id, zone_name)
            for record in records:
                if record['type'] in ['NS', 'SOA']:
                    continue

                if record['name'] == zone_name:
                    record_name = ''
                elif record['name'].endswith('.' + zone_name):
                    record_name = record['name'][:-len(zone_name)-1]
                else:
                    record_name = record['name']

                # Normalize apex/special encodings for record names used in keys/ids
                if record_name:
                    record_name = record_name.replace('\\100', '@')
                    if record_name == '@':
                        record_name = ''
                    elif record_name.endswith('.@') or record_name.endswith('.\\100'):
                        record_name = record_name.rsplit('.', 1)[0]

                terraform_key = f"{record_name} {record['type']}"
                # Use the raw FQDN from AWS for import IDs (strip trailing dot),
                # so labels like "\100" are preserved when present at apex.
                import_name_raw = record['name'].rstrip('.')
                # Escape backslashes for valid HCL string literal in imports.tf
                import_name_hcl = import_name_raw.replace('\\', r'\\')
                import_identifier = f"{zone_id}_{import_name_hcl}_{record['type']}"

                to_addr_rec = f"module.zones.module.{records_module}.aws_route53_record.this[\"{terraform_key}\"]"

                blocks.extend([
                    f"# Import record: {terraform_key}",
                    "import {",
                    f"  to = {to_addr_rec}",
                    f"  id = \"{import_identifier}\"",
                    "}",
                    "",
                ])

        if self.dry_run:
            print(f"\n[DRY RUN] Would write import blocks to: {imports_file}")
            preview = '\n'.join(blocks[:20])
            print("[DRY RUN] Import blocks preview (first 20 lines):")
            for line in preview.splitlines():
                print(f"  {line}")
            extra = max(0, len(blocks) - 20)
            if extra:
                print(f"  ... ({extra} more lines)")
            return

        # Non-dry-run: write or append, avoiding duplicates unless force
        existing_content = ""
        existing_addresses: Set[str] = set()
        if imports_file.exists() and not self.force:
            with open(imports_file, 'r') as f:
                existing_content = f.read()
            existing_addresses = self._parse_existing_imports_to_addresses(existing_content)

        # Filter blocks to avoid duplicates by 'to' address
        new_blocks: List[str] = []
        current_to: Optional[str] = None
        buffer: List[str] = []
        for line in blocks:
            if line.startswith('import {'):
                buffer = [line]
                current_to = None
                continue
            if line.startswith('  to ='):
                current_to = line.split('=', 1)[1].strip()
                buffer.append(line)
                continue
            if line == '}':
                buffer.append(line)
                buffer.append('')
                if current_to is None or current_to.strip('"') not in existing_addresses:
                    new_blocks.extend(buffer)
                buffer = []
                current_to = None
                continue
            # Regular line or comment
            if buffer:
                buffer.append(line)
            else:
                # Comments prior to first import block
                new_blocks.append(line)

        # Decide final content
        if imports_file.exists() and not self.force:
            final_content = (existing_content.rstrip() + '\n\n' + '\n'.join(new_blocks).rstrip() + '\n') if new_blocks else existing_content
        else:
            final_content = '\n'.join(blocks)

        with open(imports_file, 'w') as f:
            f.write(final_content)

        added_blocks = len([l for l in new_blocks if l == 'import {']) if (imports_file.exists() and not self.force) else len([l for l in blocks if l == 'import {'])
        print(f"✓ Wrote import blocks to {imports_file} ({added_blocks} import(s))")

    def run(self, domain: Optional[str] = None, all_domains: bool = False) -> None:
        """Run the generator for specified domain(s)."""
        if not domain and not all_domains:
            print("Error: Either --domain or --all-domains must be specified")
            sys.exit(1)
        
        # Get all zones
        print("Fetching hosted zones from AWS Route53...")
        zones = self.list_hosted_zones()
        print(f"Found {len(zones)} hosted zone(s)")
        
        if not zones:
            print("No hosted zones found in the AWS account")
            return
        
        processed = 0
        skipped = 0
        
        if domain:
            # Process single domain
            zone = next((z for z in zones if z['name'] == domain), None)
            if not zone:
                print(f"Error: Zone '{domain}' not found in Route53")
                print("Available zones:")
                for z in zones:
                    print(f"  - {z['name']}")
                sys.exit(1)
            
            if self.process_zone(zone, zones):
                processed += 1
            else:
                skipped += 1
        else:
            # Process all domains
            for zone in zones:
                if self.process_zone(zone, zones):
                    processed += 1
                else:
                    skipped += 1
        
        # Update outputs files if zones were processed
        if processed > 0:
            print("\n" + "="*50)
            print("Updating outputs files...")
            self.update_zones_outputs_file()
            self.update_root_outputs_file()
        
        # Summary
        print("\n" + "="*50)
        print("Summary:")
        print(f"  Processed: {processed} zone(s)")
        print(f"  Skipped:   {skipped} zone(s)")
        
        if processed > 0 and not self.dry_run:
            print("\nNext steps:")
            print(f"1. Review the generated Terraform files in: {self.zones_dir.absolute()}")
            print(f"2. Review the updated outputs in:")
            print(f"   - {self.zones_dir.absolute()}/outputs.tf")
            print(f"   - {self.root_dir.absolute()}/outputs.tf")
            print("3. Run 'terraform plan' to review changes")
            print("4. Import existing zones using the commands below")
            
            if self.import_blocks:
                self.generate_import_blocks()
                print("\nTip: Run 'terraform plan' to validate imports, then 'terraform apply'.")
            else:
                # Generate verification commands first
                self.generate_verification_commands()
                # Then generate import commands
                self.generate_import_commands()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate Terraform configuration files for Route53 zones',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a single domain
  python %(prog)s --domain example.com
  
  # Process all domains
  python %(prog)s --all-domains
  
  # Dry run to see what would be created
  python %(prog)s --all-domains --dry-run
  
  # Force overwrite existing files (useful for fixing errors)
  python %(prog)s --domain example.com --force
  
    # Specify custom zones directory
    python %(prog)s --all-domains --zones-dir ./custom/path
        """
    )
    
    parser.add_argument(
        '--domain',
        type=str,
        help='Process a specific domain (e.g., example.com)'
    )
    
    parser.add_argument(
        '--all-domains',
        action='store_true',
        help='Process all domains in the AWS account'
    )
    
    parser.add_argument(
        '--zones-dir',
        type=str,
        default=str(ZONES_DIR),
        help=f'Directory where zone files will be created (default: {ZONES_DIR})'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be created without making changes'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force overwrite existing zone files'
    )

    parser.add_argument(
        '--import-blocks',
        action='store_true',
        help='Generate Terraform import blocks (writes root/imports.tf)'
    )
    
    args = parser.parse_args()
    
    # Create and run generator
    generator = Route53TerraformGenerator(
        zones_dir=args.zones_dir if args.zones_dir != str(ZONES_DIR) else None,
        dry_run=args.dry_run,
        force=args.force,
        import_blocks=args.import_blocks
    )
    
    generator.run(
        domain=args.domain,
        all_domains=args.all_domains
    )


if __name__ == '__main__':
    main()