#!/bin/bash
# Deployment helper script for PDF Redactor API

set -e

echo "🚀 PDF Redactor API - Deployment Helper"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if git is initialized
if [ ! -d ".git" ]; then
    print_info "Initializing git repository..."
    git init
    print_success "Git repository initialized"
fi

# Check if .gitignore exists
if [ ! -f ".gitignore" ]; then
    print_warning ".gitignore not found"
else
    print_success ".gitignore exists"
fi

# Add all files
print_info "Adding files to git..."
git add .

# Show status
echo ""
print_info "Git status:"
git status --short

echo ""
echo "📋 Next Steps for Coolify Deployment:"
echo "======================================"
echo ""
echo "1. Commit your changes:"
echo "   ${GREEN}git commit -m 'Initial commit - PDF Redactor API'${NC}"
echo ""
echo "2. Add your remote repository:"
echo "   ${GREEN}git remote add origin https://github.com/yourusername/pdf-redactor-api.git${NC}"
echo ""
echo "3. Push to main branch:"
echo "   ${GREEN}git push -u origin main${NC}"
echo ""
echo "4. In Coolify:"
echo "   - Click '+ New Resource'"
echo "   - Select 'Public Repository' or 'Private Repository'"
echo "   - Enter your repository URL"
echo "   - Select 'Dockerfile' as build pack"
echo "   - Set port to 8000"
echo "   - Click 'Deploy'"
echo ""
echo "5. Configure environment variables in Coolify (optional):"
echo "   - HOST=0.0.0.0"
echo "   - PORT=8000"
echo "   - LOG_LEVEL=info"
echo "   - MAX_FILE_SIZE_MB=50"
echo ""
echo "📚 For detailed instructions, see: ${BLUE}COOLIFY_DEPLOYMENT.md${NC}"
echo ""
