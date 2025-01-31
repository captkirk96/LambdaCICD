import os
import sys
import json
import pytest
import boto3
import importlib.util

# Set environment variables for AWS services
os.environ['OUTPUT_BUCKET_NAME'] = 'your-output-bucket-name'
os.environ['SQS_QUEUE_URL'] = 'https://sqs.ap-south-1.amazonaws.com/278699821793/vehicle'
os.environ["AWS_REGION"] = "ap-south-1"

# Load the vehicle detection Lambda function dynamically
lambda_module_path = os.path.join(os.path.dirname(__file__), "../lambdas/stateful/car-detection-nht/lambda_function.py")

spec = importlib.util.spec_from_file_location("lambda_function", lambda_module_path)
lambda_module = importlib.util.module_from_spec(spec)
sys.modules["lambda_function"] = lambda_module
spec.loader.exec_module(lambda_module)

# Get lambda_handler function
lambda_handler = lambda_module.lambda_handler

@pytest.fixture(scope="function")
def s3_client():
    """Create an S3 client for actual bucket access."""
    return boto3.client('s3', region_name='ap-south-1')

def test_vehicle_lambda_handler(s3_client):
    """Test the vehicle detection lambda_handler function using an actual S3 image."""

    bucket_name = "frames-nht"
    image_key = "download.jpeg"  # Ensure this file exists in the S3 bucket

    # Download actual image from S3
    local_image_path = "/tmp/vehicle_sample.jpg"
    s3_client.download_file(bucket_name, image_key, local_image_path)

    with open(local_image_path, "rb") as img_file:
        image_data = img_file.read()

    # Upload the actual image to the input S3 bucket
    s3_client.put_object(
        Bucket=bucket_name,
        Key=image_key,
        Body=image_data
    )

    # Mock event structure with the actual image key
    event = {
        "Records": [
            {
                "messageId": "12345-vehicle-test",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps({
                    "Records": [
                        {
                            "eventVersion": "2.1",
                            "eventSource": "aws:s3",
                            "awsRegion": "ap-south-1",
                            "eventTime": "2025-01-27T10:39:50.206Z",
                            "eventName": "ObjectCreated:Put",
                            "userIdentity": {
                                "principalId": "AWS:TEST_USER"
                            },
                            "requestParameters": {
                                "sourceIPAddress": "192.168.1.1"
                            },
                            "responseElements": {
                                "x-amz-request-id": "TEST_REQUEST_ID",
                                "x-amz-id-2": "TEST_ID"
                            },
                            "s3": {
                                "s3SchemaVersion": "1.0",
                                "configurationId": "test-config-id",
                                "bucket": {
                                    "name": "frames-nht",
                                    "ownerIdentity": {
                                        "principalId": "TEST_OWNER"
                                    },
                                    "arn": "arn:aws:s3:::frames-nht"
                                },
                                "object": {
                                    "key": image_key,
                                    "size": 20000,
                                    "eTag": "TEST_ETAG",
                                    "sequencer": "TEST_SEQUENCER"
                                }
                            }
                        }
                    ]
                }),
                "receiptHandle": "test-receipt-handle"
            }
        ]
    }

    context = {}

    # Call the Lambda handler
    response = lambda_handler(event, context)

    # Debugging: Print the response from the handler
    print(f"Lambda response: {response}")

    assert response["statusCode"] == 200
