import json
import pytest
import boto3
from moto import mock_s3, mock_lambda, mock_sqs
from my_lambda_file import lambda_handler  # Import your Lambda function file

@pytest.fixture
def aws_credentials():
    """Mocked AWS credentials for testing"""
    boto3.setup_default_session()

@mock_s3
@mock_lambda
@mock_sqs
def test_lambda_handler():
    """Test the lambda_handler function"""
    event = {
        "Records": [
            {
                "body": json.dumps({
                    "Records": [{
                        "s3": {"bucket": {"name": "test-bucket"}, "object": {"key": "test-image.jpg"}}
                    }]
                }),
                "receiptHandle": "test-receipt-handle"
            }
        ]
    }
    context = {}
    response = lambda_handler(event, context)
    assert response["statusCode"] == 200
