"""
Test Runner Service

This module wraps the core test validation and running logic from test_validation_service
to provide a dedicated entry point for executing test suites.
"""

from app.services.test_validation_service import validate_generated_file, validate_and_repair_batch

def run_tests_for_file(*args, **kwargs):
    """Executes the test suite for a specific generated file."""
    return validate_generated_file(*args, **kwargs)

def run_test_suite(*args, **kwargs):
    """Executes the test suite for a batch of generated files."""
    return validate_and_repair_batch(*args, **kwargs)
