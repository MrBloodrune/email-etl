#!/bin/bash

# Initialize Email ETL Git Repository
# Run this AFTER setup-git-global.sh

echo "=== Initializing Email ETL Git Repository ==="
echo ""

# Test GitHub connection first
echo "Testing GitHub SSH connection..."
ssh -T git@github.com

if [ $? -ne 1 ]; then
    echo "ERROR: GitHub SSH connection failed!"
    echo "Please ensure you've:"
    echo "1. Run setup-git-global.sh"
    echo "2. Added your SSH key to GitHub"
    exit 1
fi

echo ""
echo "GitHub connection successful!"
echo ""

# Initialize git repository
echo "Initializing git repository..."
git init

# Create .gitignore if it doesn't exist
if [ ! -f .gitignore ]; then
    echo "Creating .gitignore..."
    cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Environment files
.env
.env.local
.env.*.local

# Credentials
credentials.json
token.json
*.pem
*.key

# OAuth tokens
tokens/

# Data files
emails/
*.db
*.sqlite
*.sql

# Logs
logs/
*.log

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Docker volumes data
postgres_data/
pgadmin_data/

# Temp files
*.tmp
*.temp
*.bak

# Distribution
dist/
build/
*.egg-info/
EOF
fi

# Add all files
echo "Adding files to git..."
git add .

# Show status
echo ""
echo "Git status:"
git status

echo ""
echo "Creating initial commit..."
git commit -m "Initial commit: Multi-provider email ETL pipeline with Docker support

- Plugin-based architecture for multiple email providers
- Gmail provider implemented with OAuth2
- PostgreSQL with pgvector for semantic search
- Markdown storage for email archives
- LLM integration for Q&A and analysis
- Docker support with persistent storage
- FastAPI REST API
- Optional observability with Grafana Alloy"

# Set main branch
echo ""
echo "Setting main branch..."
git branch -M main

# Add remote origin
echo ""
echo "Adding remote origin..."
git remote add origin git@github.com:MrBloodrune/email-etl.git

# Show remote
echo ""
echo "Remote configuration:"
git remote -v

echo ""
echo "Ready to push! Run the following command when ready:"
echo "git push -u origin main"
echo ""
echo "If this is a new repository, make sure to create it on GitHub first:"
echo "1. Go to https://github.com/new"
echo "2. Create repository named 'email-etl'"
echo "3. Don't initialize with README, .gitignore or license"
echo "4. Then run: git push -u origin main"