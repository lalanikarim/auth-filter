#!/usr/bin/env python3
"""
Retag the latest image from current registry to a new registry URL.
"""

import os
import subprocess
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_environment_variables():
    """Get required environment variables with defaults."""
    registry_url = os.getenv('REGISTRY_URL')
    if not registry_url:
        print("❌ REGISTRY_URL environment variable is required")
        print("Example: export REGISTRY_URL=localhost:5000/k8s/auth-filter")
        print("Or add REGISTRY_URL=your-registry-url to your .env file")
        sys.exit(1)
    
    container_tool = os.getenv('CONTAINER_TOOL', 'podman')
    if container_tool not in ['docker', 'podman']:
        print(f"❌ CONTAINER_TOOL must be 'docker' or 'podman', got: {container_tool}")
        sys.exit(1)
    
    return registry_url, container_tool


def get_latest_built_tag(registry_url, container_tool):
    """Get the latest built tag from the registry."""
    today = datetime.now().strftime('%Y%m%d')
    date_prefix = f"{today}."
    
    # Get existing tags for today
    try:
        result = subprocess.run(
            [container_tool, 'images', '--format', '{{.Tag}}', registry_url],
            capture_output=True, text=True, check=True
        )
        existing_tags = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        # Filter tags that start with today's date
        today_tags = [tag for tag in existing_tags if tag.startswith(date_prefix)]
        
        if not today_tags:
            print("❌ No built images found for today")
            print("💡 Run 'uv run build-image' first to build an image")
            sys.exit(1)
        
        # Find the highest build number
        build_numbers = []
        for tag in today_tags:
            try:
                parts = tag.split('.')
                if len(parts) >= 2:
                    build_num = int(parts[1])
                    build_numbers.append(build_num)
            except (ValueError, IndexError):
                continue
        
        if not build_numbers:
            print("❌ No valid build tags found for today")
            sys.exit(1)
        
        latest_build = max(build_numbers)
        return f"{today}.{latest_build}"
        
    except subprocess.CalledProcessError:
        print("❌ Failed to get image tags")
        print("💡 Run 'uv run build-image' first to build an image")
        sys.exit(1)


def get_next_build_number_for_target(registry_url, container_tool):
    """Get the next build number for the target registry."""
    today = datetime.now().strftime('%Y%m%d')
    date_prefix = f"{today}."
    
    # Get existing tags for today from target registry
    try:
        result = subprocess.run(
            [container_tool, 'images', '--format', '{{.Tag}}', registry_url],
            capture_output=True, text=True, check=True
        )
        existing_tags = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        # Filter tags that start with today's date
        today_tags = [tag for tag in existing_tags if tag.startswith(date_prefix)]
        
        if not today_tags:
            return 1
        
        # Extract build numbers and find the highest
        build_numbers = []
        for tag in today_tags:
            try:
                parts = tag.split('.')
                if len(parts) >= 2:
                    build_num = int(parts[1])
                    build_numbers.append(build_num)
            except (ValueError, IndexError):
                continue
        
        return max(build_numbers) + 1 if build_numbers else 1
        
    except subprocess.CalledProcessError:
        # If no images exist yet, start with 1
        return 1


def retag_image(source_registry, target_registry, source_tag, target_tag, container_tool):
    """Retag the image from source to target registry."""
    print(f"🏷️  Retagging image:")
    print(f"   From: {source_registry}:{source_tag}")
    print(f"   To: {target_registry}:{target_tag}")
    
    # Retag the image
    retag_cmd = [
        container_tool, 'tag',
        f"{source_registry}:{source_tag}",
        f"{target_registry}:{target_tag}"
    ]
    
    print(f"Running: {' '.join(retag_cmd)}")
    result = subprocess.run(retag_cmd, check=True)
    
    if result.returncode != 0:
        print("❌ Retag failed")
        sys.exit(1)
    
    print("✅ Retag successful")
    
    # Also retag as latest
    latest_retag_cmd = [
        container_tool, 'tag',
        f"{source_registry}:{source_tag}",
        f"{target_registry}:latest"
    ]
    
    print(f"Running: {' '.join(latest_retag_cmd)}")
    result = subprocess.run(latest_retag_cmd, check=True)
    
    if result.returncode != 0:
        print("❌ Latest retag failed")
        sys.exit(1)
    
    print("✅ Latest retag successful")


def update_registry_url_env(new_registry_url):
    """Update the REGISTRY_URL environment variable."""
    print(f"🔄 Updating REGISTRY_URL to: {new_registry_url}")
    print()
    print("💡 To make this permanent, run:")
    print(f"   export REGISTRY_URL=\"{new_registry_url}\"")
    print("Or add to your .env file:")
    print(f"   REGISTRY_URL=\"{new_registry_url}\"")
    print()
    print("💡 To push the retagged image, run:")
    print("   uv run push-image")


def main():
    """Main function."""
    try:
        # Check command line arguments
        if len(sys.argv) != 2:
            print("❌ Usage: uv run retag-latest <new-registry-url>")
            print("Example: uv run retag-latest registry.infinidigm.com/k8s/auth-filter")
            sys.exit(1)
        
        new_registry_url = sys.argv[1]
        
        print("🚀 Starting image retag process...")
        
        # Get environment variables
        current_registry_url, container_tool = get_environment_variables()
        
        print(f"🐳 Container tool: {container_tool}")
        print(f"📦 Current registry: {current_registry_url}")
        print(f"📦 Target registry: {new_registry_url}")
        print()
        
        # Get the latest built tag from current registry
        latest_source_tag = get_latest_built_tag(current_registry_url, container_tool)
        print(f"🏷️  Found latest source tag: {latest_source_tag}")
        
        # Generate new tag for target registry
        today = datetime.now().strftime('%Y%m%d')
        new_build_number = get_next_build_number_for_target(new_registry_url, container_tool)
        new_tag = f"{today}.{new_build_number}"
        print(f"🏷️  Generated target tag: {new_tag}")
        print()
        
        # Retag the image
        retag_image(current_registry_url, new_registry_url, latest_source_tag, new_tag, container_tool)
        
        print()
        print("🎉 Success! Image retagged:")
        print(f"   - {new_registry_url}:{new_tag}")
        print(f"   - {new_registry_url}:latest")
        print()
        
        # Provide instructions for next steps
        update_registry_url_env(new_registry_url)
        
    except KeyboardInterrupt:
        print("\n❌ Retag cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 