"""Main entry point for the feed processor package."""

import sys
from pathlib import Path

# Add the parent directory to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from feed_processor.cli import cli

if __name__ == "__main__":
    cli()
