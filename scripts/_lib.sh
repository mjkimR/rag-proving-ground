#!/usr/bin/env bash
# scripts/_lib.sh — Shared helpers for module resolution in rag-proving-ground
# Source this file from other scripts: source "$(dirname "$0")/_lib.sh"

AVAILABLE_MODULES="all backend web"

resolve_module() {
    case "$1" in
        backend|back|api) echo "backend" ;;
        web|front|frontend|ui) echo "web" ;;
        all) echo "all" ;;
        *) echo "$1" ;;
    esac
}

resolve_module_path() {
    case "$1" in
        backend) echo "apps/backend" ;;
        web) echo "apps/web" ;;
        *) echo "apps/$1" ;;
    esac
}

should_run() { [ "$1" = "all" ] || [ "$1" = "$2" ]; }
