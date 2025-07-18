#!/usr/bin/env python3
"""
Push Docker/Podman images to registry.
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
        print("Example: export REGISTRY_URL=registry.infinidigm.com/k8s/auth-filter")
        print("Or add REGISTRY_URL=your-registry-url to your .env file")
        sys.exit(1)
    
    container_tool = os.getenv('CONTAINER_TOOL', 'podman')
    if container_tool not in ['docker', 'podman']:
        print(f"❌ CONTAINER_TOOL must be 'docker' or 'podman', got: {container_tool}")
        sys.exit(1)
    
    return registry_url, container_tool


def get_latest_built_tag(registry_url, container_tool):
    """Get the latest built tag for today's date."""
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


def push_image(registry_url, container_tool, tag):
    """Push the image with the given tag."""
    print(f"📤 Pushing image: {registry_url}:{tag}")
    
    push_cmd = [container_tool, 'push', f"{registry_url}:{tag}"]
    
    print(f"Running: {' '.join(push_cmd)}")
    result = subprocess.run(push_cmd, check=True)
    
    if result.returncode != 0:
        print(f"❌ Push failed for tag: {tag}")
        sys.exit(1)
    
    print(f"✅ Push successful for tag: {tag}")


def push_latest(registry_url, container_tool):
    """Push the latest tag."""
    print(f"📤 Pushing image: {registry_url}:latest")
    
    push_cmd = [container_tool, 'push', f"{registry_url}:latest"]
    
    print(f"Running: {' '.join(push_cmd)}")
    result = subprocess.run(push_cmd, check=True)
    
    if result.returncode != 0:
        print("❌ Push failed for tag: latest")
        sys.exit(1)
    
    print("✅ Push successful for tag: latest")


def main():
    """Main function."""
    try:
        print("🚀 Starting image push process...")
        
        # Get environment variables
        registry_url, container_tool = get_environment_variables()
        
        print(f"🐳 Container tool: {container_tool}")
        print(f"📦 Registry: {registry_url}")
        print()
        
        # Get the latest built tag
        latest_tag = get_latest_built_tag(registry_url, container_tool)
        print(f"🏷️  Found latest built tag: {latest_tag}")
        print()
        
        # Push both the specific tag and latest
        push_image(registry_url, container_tool, latest_tag)
        push_latest(registry_url, container_tool)
        
        print()
        print("🎉 Success! Image pushed with tags:")
        print(f"   - {registry_url}:{latest_tag}")
        print(f"   - {registry_url}:latest")
        
    except KeyboardInterrupt:
        print("\n❌ Push cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 