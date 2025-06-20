#!/bin/bash

# Git Global Setup Script
# This sets up git globally for your server

echo "=== Git Global Configuration Setup ==="
echo ""

# Install git if not already installed
echo "1. Installing git..."
sudo dnf install git -y

echo ""
echo "2. Setting up global git configuration..."

# Set your git user info (replace with your actual info)
read -p "Enter your GitHub username: " github_username
read -p "Enter your GitHub email: " github_email

git config --global user.name "$github_username"
git config --global user.email "$github_email"

echo ""
echo "3. Setting up SSH key for GitHub..."
echo ""

# Check if SSH key already exists
if [ -f ~/.ssh/id_ed25519 ]; then
    echo "SSH key already exists at ~/.ssh/id_ed25519"
    echo "Using existing key..."
else
    echo "Generating new SSH key..."
    ssh-keygen -t ed25519 -C "$github_email" -f ~/.ssh/id_ed25519
fi

echo ""
echo "4. Starting SSH agent and adding key..."
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

echo ""
echo "5. Your SSH public key (add this to GitHub):"
echo "================================================"
cat ~/.ssh/id_ed25519.pub
echo "================================================"
echo ""
echo "Copy the above key and add it to GitHub:"
echo "1. Go to https://github.com/settings/keys"
echo "2. Click 'New SSH key'"
echo "3. Paste the key and save"
echo ""

# Configure SSH for GitHub
echo "6. Configuring SSH for GitHub..."
mkdir -p ~/.ssh
cat > ~/.ssh/config << 'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519
    AddKeysToAgent yes
EOF

chmod 600 ~/.ssh/config

echo ""
echo "7. Git configuration summary:"
git config --global --list

echo ""
echo "Setup complete! You can now test the connection with:"
echo "ssh -T git@github.com"