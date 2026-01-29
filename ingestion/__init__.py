"""Offline ingestion service for Confluence → Azure AI Search (RAG)."""
from .config import IngestionConfig

__all__ = ["IngestionConfig"]

# Run pipeline: from ingestion.ingest import run_ingestion
# CLI (from project root): python -m ingestion
