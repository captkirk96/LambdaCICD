import sys
import os
import json
import pytest
import boto3
import importlib.util
from moto import mock_aws

# Setting environment variables required for the Lambda function
os.environ['OUTPUT_BUCKET_NAME'] = 'mock-output-bucket'
os.environ['INVOKE_FUNCTION_ARN'] = 'arn:aws:lambda:ap-south-1:123456789012:function:next-lambda-function'
os.environ['SQS_QUEUE_URL'] = 'https://sqs.mock.amazonaws.com/123456789012/test-queue'

# Manually load the Lambda function
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
                    }]}
                ),
                "receiptHandle": "test-receipt-handle"
            }
        ]
    }
    context = {}

    # Call the Lambda handler
    response = lambda_handler(event, context)

    # Print the Lambda response
    print(f"Lambda function output:\n{json.dumps(response, indent=2)}")

    # Validate the response
    assert response["statusCode"] == 200
