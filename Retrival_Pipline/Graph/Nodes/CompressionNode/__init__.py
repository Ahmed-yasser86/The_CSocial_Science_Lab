"""
Compression Node Package

This package contains functions for compressing intelligence reports
to provide context for downstream nodes in the intelligence graph.
"""

from .research_compressor_node import (
    compress_intelligence_report,
    compress_subject_intelligence,
    format_compressed_for_injection,
    CompressedIntelligence
)

__all__ = [
    "compress_intelligence_report",
    "compress_subject_intelligence",
    "format_compressed_for_injection", 
    "CompressedIntelligence"
]