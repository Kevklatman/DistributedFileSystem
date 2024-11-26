#!/usr/bin/env python3
import os
import sys
import json
import shutil
from pathlib import Path
import base64
from typing import Dict, Any
import argparse

def validate_credentials(creds: Dict[str, Any], provider: str) -> bool:
    """Validate provider-specific credentials."""
    if provider == 'gcp':
        required_fields = [
            'type', 'project_id', 'private_key_id', 'private_key',
            'client_email', 'client_id', 'auth_uri', 'token_uri'
        ]
        return all(field in creds for field in required_fields)
    return False

def setup_credentials(args):
    """Set up credentials securely."""
    # Create secure credentials directory
    secure_creds_dir = Path.home() / '.dfs' / 'credentials'
    secure_creds_dir.mkdir(parents=True, exist_ok=True)
    
    # Set restrictive permissions
    os.chmod(secure_creds_dir, 0o700)
    
    if args.provider == 'gcp':
        # Read and validate GCP credentials
        try:
            with open(args.credentials_file, 'r') as f:
                creds = json.load(f)
                
            if not validate_credentials(creds, 'gcp'):
                print("Error: Invalid GCP credentials format")
                sys.exit(1)
                
            # Save to secure location
            secure_creds_file = secure_creds_dir / 'gcp-service-account.json'
            with open(secure_creds_file, 'w') as f:
                json.dump(creds, f, indent=2)
            
            # Set restrictive permissions
            os.chmod(secure_creds_file, 0o600)
            
            # Update .env file
            env_path = Path(args.env_file)
            env_content = []
            
            if env_path.exists():
                with open(env_path, 'r') as f:
                    env_content = f.readlines()
            
            # Update or add GCP credentials path
            gcp_creds_line = f'GOOGLE_APPLICATION_CREDENTIALS={secure_creds_file}\n'
            gcp_project_line = f'GOOGLE_CLOUD_PROJECT={creds["project_id"]}\n'
            
            # Remove existing GCP credential lines
            env_content = [line for line in env_content 
                         if not line.startswith(('GOOGLE_APPLICATION_CREDENTIALS=',
                                               'GOOGLE_CLOUD_PROJECT='))]
            
            # Add new GCP credential lines
            env_content.extend([gcp_creds_line, gcp_project_line])
            
            # Write updated .env file
            with open(env_path, 'w') as f:
                f.writelines(env_content)
            
            print(f"\n✅ GCP credentials securely stored at: {secure_creds_file}")
            print(f"✅ Environment file updated: {env_path}")
            print("\n⚠️  Important security notes:")
            print("1. The credentials file has been moved to a secure location")
            print("2. File permissions have been set to 600 (user read/write only)")
            print("3. The original credentials file should be deleted")
            print(f"4. Make sure {secure_creds_file} is backed up securely")
            
            # Create example credentials file
            example_creds = {
                "type": "service_account",
                "project_id": "your-project-id",
                "private_key_id": "your-key-id",
                "private_key": "your-private-key",
                "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
                "client_id": "your-client-id",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/your-service-account"
            }
            
            example_file = Path('credentials/gcp-service-account.example.json')
            example_file.parent.mkdir(parents=True, exist_ok=True)
            with open(example_file, 'w') as f:
                json.dump(example_creds, f, indent=2)
            
            print(f"\n✅ Created example credentials file: {example_file}")
            
            if args.delete_original:
                try:
                    os.remove(args.credentials_file)
                    print(f"✅ Deleted original credentials file: {args.credentials_file}")
                except Exception as e:
                    print(f"⚠️  Warning: Could not delete original file: {e}")
            
        except Exception as e:
            print(f"Error setting up credentials: {e}")
            sys.exit(1)
    else:
        print(f"Error: Unsupported provider: {args.provider}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Secure credential setup for DFS')
    parser.add_argument('--provider', required=True, choices=['gcp'],
                      help='Cloud provider (currently only supports gcp)')
    parser.add_argument('--credentials-file', required=True,
                      help='Path to the credentials file')
    parser.add_argument('--env-file', default='.env',
                      help='Path to the environment file (default: .env)')
    parser.add_argument('--delete-original', action='store_true',
                      help='Delete the original credentials file after setup')
    
    args = parser.parse_args()
    setup_credentials(args)
