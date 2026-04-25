"""Layer 1: Organization knowledge base.

Pipeline: parse -> chunk -> embed -> store -> retrieve (with citations).
"""

from kb.retrieval import retrieve
from kb.ingest import ingest_path

__all__ = ["retrieve", "ingest_path"]
