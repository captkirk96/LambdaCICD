import sys
import os
import json
import pytest
import boto3
import importlib.util
from moto import mock_aws  # Use mock_aws instead of individual service mocks

# Debugging: Print the current working directory
print(f"Current working directory: {os.getcwd()}")

# Manually load the module using importlib (for hyphenated directories)
lambda_module_path = os.path.join(os.path.dirname(__file__), "../lambdas/stateful/person-detection-nht/lambda_function.py")

spec = importlib.util.spec_from_file_location("lambda_function", lambda_module_path)
lambda_module = importlib.util.module_from_spec(spec)
sys.modules["lambda_function"] = lambda_module
spec.loader.exec_module(lambda_module)

# Now, you can use lambda_handler from the dynamically imported module
lambda_handler = lambda_module.lambda_handler

@pytest.fixture
def aws_credentials():
    """Mocked AWS credentials for testing"""
    boto3.setup_default_session()

@mock_aws
def test_lambda_handler():
    """Test the lambda_handler function"""
    event = {
        "Records": [
            {
                "body": json.dumps({
                    "Records": [{
                        "s3": {
                            "bucket": {"name": "input-frames"},
                            "object": {"key": "test.jpg"}
                        }
                    }]
                }),
                "receiptHandle": "test-receipt-handle"
            }
        ]
    }
    context = {}

    # Debugging: Print the event and context being passed to the handler
    print(f"Event: {json.dumps(event, indent=2)}")
    print(f"Context: {context}")

    # Call the Lambda handler
    response = lambda_handler(event, context)

    # Debugging: Print the response from the handler
    print(f"Lambda response: {response}")

    assert response["statusCode"] == 200
