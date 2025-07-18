#!/usr/bin/env python3
"""
Build Docker/Podman images with smart tag generation.
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


def get_next_build_number(registry_url, container_tool):
    """Get the next build number for today's date."""
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


def build_image(registry_url, container_tool, tag):
    """Build the image with the given tag."""
    print(f"🔨 Building image: {registry_url}:{tag}")
    
    # Build the image
    build_cmd = [
        container_tool, 'build', '.',
        '--platform=linux/amd64',
        '-t', f"{registry_url}:{tag}",
        '-t', f"{registry_url}:latest"
    ]
    
    print(f"Running: {' '.join(build_cmd)}")
    result = subprocess.run(build_cmd, check=True)
    
    if result.returncode != 0:
        print("❌ Build failed")
        sys.exit(1)
    
    print(f"✅ Build successful")
    return tag


def main():
    """Main function."""
    try:
        print("🚀 Starting image build process...")
        
        # Get environment variables
        registry_url, container_tool = get_environment_variables()
        
        # Generate smart tag
        today = datetime.now().strftime('%Y%m%d')
        build_number = get_next_build_number(registry_url, container_tool)
        tag = f"{today}.{build_number}"
        
        print(f"📅 Date: {today}")
        print(f"🔢 Build number: {build_number}")
        print(f"🏷️  Generated tag: {tag}")
        print(f"🐳 Container tool: {container_tool}")
        print(f"📦 Registry: {registry_url}")
        print()
        
        # Build the image
        built_tag = build_image(registry_url, container_tool, tag)
        
        print()
        print("🎉 Success! Image built with tags:")
        print(f"   - {registry_url}:{built_tag}")
        print(f"   - {registry_url}:latest")
        print()
        print("💡 To push the image, run: uv run push-image")
        
    except KeyboardInterrupt:
        print("\n❌ Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 