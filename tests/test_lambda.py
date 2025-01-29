import json
import pytest
import os
import boto3
from moto import mock_s3, mock_sqs, mock_lambda
from unittest.mock import patch

# Setting up mock AWS credentials
os.environ['AWS_ACCESS_KEY_ID'] = 'mock_access_key'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'mock_secret_key'

os.environ['OUTPUT_BUCKET_NAME'] = 'mock-output-bucket'
os.environ['INVOKE_FUNCTION_ARN'] = 'arn:aws:lambda:ap-south-1:123456789012:function:next-lambda-function'

@mock_sqs
@mock_s3
@mock_lambda
def test_lambda_handler():
    # Mock SQS queue creation
    sqs = boto3.client('sqs', region_name='ap-south-1')
    queue_url = sqs.create_queue(QueueName='test-queue')['QueueUrl']
    os.environ['SQS_QUEUE_URL'] = queue_url  # Set environment variable for the queue URL

    # Mock S3 bucket creation and file upload
    s3 = boto3.client('s3', region_name='us-west-2')
    s3.create_bucket(Bucket='input-frames')
    s3.put_object(Bucket='input-frames', Key='test.jpg', Body=b'fake-image-data')

    # Setup event and context
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

    # Patch the Modal API request
    with patch('requests.post') as mock_modal_post:
        # Mock the Modal response
        mock_modal_post.return_value.status_code = 200
        mock_modal_post.return_value.json.return_value = {"human_detected": True}

        # Call the Lambda handler
        response = lambda_handler(event, context)

        # Print the Lambda response
        print(f"Lambda function output:\n{json.dumps(response, indent=2)}")

        # Validate the response
        assert response["statusCode"] == 200
        mock_modal_post.assert_called_once()

        # Ensure the Lambda invocation happens (if any)
        lambda_client = boto3.client('lambda')
        lambda_client.invoke.assert_called_once()

