import json
import pytest
import boto3
from moto import mock_aws
from lambda_function import lambda_handler  # Update with your actual Lambda filename

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
                        "s3": {"bucket": {"name": "input-frames"}, "object": {"key": "test.jpg"}}
                    }]
                }),
                "receiptHandle": "test-receipt-handle"
            }
        ]
    }
    context = {}
    response = lambda_handler(event, context)
    assert response["statusCode"] == 200
