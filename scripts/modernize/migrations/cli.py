#!/usr/bin/env python3
"""CLI entry point for the migration registry (issue #9).

See scripts/modernize/migrations/registry.py for the actual logic; this is
just a thin, stable `python3 -m scripts.modernize.migrations.cli` entry
point for Make targets and CI.
"""
import sys

from scripts.modernize.migrations.registry import main

if __name__ == "__main__":
    sys.exit(main())
