#!/bin/bash
# Example usage of the image build, push, and retag scripts using uv run

# Option 1: Set environment variables in shell
export REGISTRY_URL="localhost:5000/k8s/auth-filter"
export CONTAINER_TOOL="podman"  # or "docker"

# Option 2: Use .env file (recommended)
# Create a .env file in your project root with:
# REGISTRY_URL=localhost:5000/k8s/auth-filter
# CONTAINER_TOOL=podman

# Show available commands
echo "Available commands:"
echo "  uv run build-image         - Build Docker/Podman image with smart tag generation"
echo "  uv run push-image          - Push the latest built image to registry"
echo "  uv run build-and-push-image - Build and push image in one command"
echo "  uv run retag-latest <url>  - Retag latest image to new registry URL"
echo "  uv run dev                 - Start development server"
echo "  uv run test                - Run tests"
echo "  uv run migrate             - Run database migrations"
echo ""
echo "Environment variables (can be set in shell or .env file):"
echo "  REGISTRY_URL     - Registry URL (required, e.g., localhost:5000/k8s/auth-filter)"
echo "  CONTAINER_TOOL   - Container tool to use (default: podman, options: docker, podman)"
echo ""
echo "Example .env file:"
echo "  REGISTRY_URL=localhost:5000/k8s/auth-filter"
echo "  CONTAINER_TOOL=podman"

echo ""
echo "=== Development Workflow ==="
echo "Step 1: Build and push to local dev registry multiple times"
echo "Building image..."
uv run build-and-push-image

echo ""
echo "Step 2: Build another version for testing"
echo "Building another image..."
uv run build-and-push-image

echo ""
echo "=== Promotion Workflow ==="
echo "Step 3: Retag latest to staging registry"
echo "Retagging to staging..."
uv run retag-latest staging-registry.example.com/k8s/auth-filter

echo ""
echo "Step 4: Update REGISTRY_URL and push to staging"
export REGISTRY_URL="staging-registry.example.com/k8s/auth-filter"
echo "Pushing to staging..."
uv run push-image

echo ""
echo "Step 5: Retag latest to production registry"
echo "Retagging to production..."
uv run retag-latest registry.infinidigm.com/k8s/auth-filter

echo ""
echo "Step 6: Update REGISTRY_URL and push to production"
export REGISTRY_URL="registry.infinidigm.com/k8s/auth-filter"
echo "Pushing to production..."
uv run push-image

# Example output for build-and-push-image:
# 🚀 Starting image build and push process...
# 📅 Date: 20250718
# 🔢 Build number: 1
# 🏷️  Generated tag: 20250718.1
# 🐳 Container tool: podman
# 📦 Registry: localhost:5000/k8s/auth-filter
# 
# 🔨 Building image: localhost:5000/k8s/auth-filter:20250718.1
# Running: podman build . --platform=linux/amd64 -t localhost:5000/k8s/auth-filter:20250718.1 -t localhost:5000/k8s/auth-filter:latest
# ✅ Build successful
# 
# 📤 Pushing image: localhost:5000/k8s/auth-filter:20250718.1
# ✅ Push successful for tag: 20250718.1
# 📤 Pushing image: localhost:5000/k8s/auth-filter:latest
# ✅ Push successful for tag: latest
# 
# 🎉 Success! Image built and pushed with tags:
#    - localhost:5000/k8s/auth-filter:20250718.1
#    - localhost:5000/k8s/auth-filter:latest

# Example output for retag-latest:
# 🚀 Starting image retag process...
# 🐳 Container tool: podman
# 📦 Current registry: localhost:5000/k8s/auth-filter
# 📦 Target registry: staging-registry.example.com/k8s/auth-filter
# 
# 🏷️  Found latest source tag: 20250718.2
# 🏷️  Generated target tag: 20250718.1
# 
# 🏷️  Retagging image:
#    From: localhost:5000/k8s/auth-filter:20250718.2
#    To: staging-registry.example.com/k8s/auth-filter:20250718.1
# Running: podman tag localhost:5000/k8s/auth-filter:20250718.2 staging-registry.example.com/k8s/auth-filter:20250718.1
# ✅ Retag successful
# Running: podman tag localhost:5000/k8s/auth-filter:20250718.2 staging-registry.example.com/k8s/auth-filter:latest
# ✅ Latest retag successful
# 
# 🎉 Success! Image retagged:
#    - staging-registry.example.com/k8s/auth-filter:20250718.1
#    - staging-registry.example.com/k8s/auth-filter:latest
# 
# 🔄 Updating REGISTRY_URL to: staging-registry.example.com/k8s/auth-filter
# 
# 💡 To make this permanent, run:
#    export REGISTRY_URL="staging-registry.example.com/k8s/auth-filter"
# Or add to your .env file:
#    REGISTRY_URL="staging-registry.example.com/k8s/auth-filter"
# 
# 💡 To push the retagged image, run:
#    uv run push-image

# Example output for push-image:
# 🚀 Starting image push process...
# 🐳 Container tool: podman
# 📦 Registry: staging-registry.example.com/k8s/auth-filter
# 
# 🏷️  Found latest built tag: 20250718.1
# 
# 📤 Pushing image: staging-registry.example.com/k8s/auth-filter:20250718.1
# ✅ Push successful for tag: 20250718.1
# 📤 Pushing image: staging-registry.example.com/k8s/auth-filter:latest
# ✅ Push successful for tag: latest
# 
# 🎉 Success! Image pushed with tags:
#    - staging-registry.example.com/k8s/auth-filter:20250718.1
#    - staging-registry.example.com/k8s/auth-filter:latest

# Other useful commands:
# uv run dev              # Start development server
# uv run test             # Run tests
# uv run migrate          # Run database migrations
# uv run pytest --watch   # Run tests in watch mode
# uv run alembic revision --autogenerate -m "add new table"  # Create new migration
# uv run alembic downgrade -1  # Downgrade last migration 