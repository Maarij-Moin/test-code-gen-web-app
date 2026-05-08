"""
Test Writer Service

This module wraps the core test generation logic from test_generation_service
to provide a dedicated entry point for writing and committing tests.
"""

from app.services.test_generation_service import generate_test_file, GeneratedTestFile

def write_test_file(*args, **kwargs) -> GeneratedTestFile:
    """Delegates to generate_test_file to generate and write the test to disk."""
    return generate_test_file(*args, **kwargs)
