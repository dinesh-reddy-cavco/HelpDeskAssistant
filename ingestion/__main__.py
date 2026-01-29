"""
CLI entry point. Run from project root: python -m ingestion
"""
import sys
from .ingest import main

if __name__ == "__main__":
    sys.exit(main())
