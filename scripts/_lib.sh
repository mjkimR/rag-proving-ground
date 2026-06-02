#!/usr/bin/env bash
# scripts/_lib.sh — Shared helpers for module resolution in rag-proving-ground
# Source this file from other scripts: source "$(dirname "$0")/_lib.sh"

AVAILABLE_MODULES="all backend web"

resolve_module() {
    case "$1" in
        backend|back|api) echo "backend" ;;
        web|front|frontend|ui) echo "web" ;;
        all) echo "all" ;;
        *)
            echo "Unknown module '$1'. Expected one of: $AVAILABLE_MODULES" >&2
            exit 2
            ;;
    esac
}

resolve_module_path() {
    case "$1" in
        backend) echo "apps/backend" ;;
        web) echo "apps/web" ;;
        *)
            echo "Unknown module path '$1'. Expected one of: backend web" >&2
            exit 2
            ;;
    esac
}

should_run() { [ "$1" = "all" ] || [ "$1" = "$2" ]; }
