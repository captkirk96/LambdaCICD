
import os
import sys
import pytest
from unittest.mock import patch

# Add the current directory to the system path to ensure all test modules are discoverable
sys.path.insert(0, os.path.dirname(__file__))

# Import all test modules to make sure they are included in the test suite
from . import test_extract_frame
from . import test_lambda

# Verify AWS resources mocking setup is accessible
@pytest.fixture(scope="session", autouse=True)
def setup_aws_mocks():
    """Setup AWS mocks for all tests."""
    with patch('boto3.client') as mock:
        yield mock

# Ensure consistency in test organization and execution
def pytest_configure(config):
    """Configure pytest to ensure consistent test execution."""
    config.addinivalue_line("markers", "aws: mark test as using AWS resources")

# Ensure the test suite is properly configured for execution and reporting
def pytest_report_header(config):
    """Add custom header to pytest report."""
    return "Project: LambdaCICD Test Suite"

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Add custom summary to pytest report."""
    terminalreporter.section("Summary")
    terminalreporter.write_line(f"Exit Status: {exitstatus}")