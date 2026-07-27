"""Allow `python3 -m scripts.upstream_port ...` as the documented entry point."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
