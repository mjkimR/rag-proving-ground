#!/usr/bin/env bash
# Install 'just' command runner
set -e

INSTALL_DIR="${1:-/usr/local/bin}"

if command -v just &>/dev/null; then
    echo "just is already installed: $(just --version)"
    exit 0
fi

install_via_curl() {
    echo "Installing just via official installer (curl)..."
    curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to "$INSTALL_DIR"
}

OS="$(uname -s)"

case "$OS" in
    Darwin)
        if command -v brew &>/dev/null; then
            echo "Installing just via Homebrew..."
            brew install just
        else
            install_via_curl
        fi
        ;;
    Linux)
        if command -v brew &>/dev/null; then
            echo "Installing just via Homebrew..."
            brew install just
        elif command -v apt-get &>/dev/null; then
            echo "Installing just via apt..."
            sudo apt-get update -qq
            sudo apt-get install -y just
        elif command -v pacman &>/dev/null; then
            echo "Installing just via pacman..."
            sudo pacman -S --noconfirm just
        else
            install_via_curl
        fi
        ;;
    *)
        echo "Unsupported OS: $OS — falling back to official installer..."
        install_via_curl
        ;;
esac

echo "just installed successfully: $(just --version)"
