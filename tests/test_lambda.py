import sys
import os
import json
import pytest
import boto3
from moto import mock_aws

# Debugging: Print the current working directory
print(f"Current working directory: {os.getcwd()}")



# Import the lambda function handler
from lambdas.stateful.person_detection_nht.lambda_function import lambda_handler

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
