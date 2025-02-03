import os
import sys
import json
import pytest
import boto3
import importlib.util

# Set environment variables
os.environ['OUTPUT_BUCKET_NAME'] = 'your-output-bucket-name'
os.environ["AWS_REGION"] = "ap-south-1"

# Manually load the module using importlib
lambda_module_path = os.path.join(os.path.dirname(__file__), "../lambdas/stateful/fall-detection/lambda_function.py")

spec = importlib.util.spec_from_file_location("lambda_function", lambda_module_path)
lambda_module = importlib.util.module_from_spec(spec)
sys.modules["lambda_function"] = lambda_module
spec.loader.exec_module(lambda_module)

# Now, you can use lambda_handler from the dynamically imported module
lambda_handler = lambda_module.lambda_handler

@pytest.fixture(scope="function")
def s3_client():
    """Create an S3 client for actual bucket access."""
    return boto3.client('s3', region_name='ap-south-1')

def test_lambda_handler(s3_client):
    """Test the lambda_handler function using an actual S3 image."""

    bucket_name = "frames-nht"
    image_key = "test.jpg"  # Ensure this file exists in S3

    # Download actual image from S3
    local_image_path = "/tmp/fall_sample.jpg"
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
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": "ap-south-1",
                "eventTime": "2025-01-27T10:39:50.206Z",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "s3SchemaVersion": "1.0",
                    "configurationId": "test-config",
                    "bucket": {
                        "name": "frames-nht",
                        "arn": "arn:aws:s3:::frames-nht"
                    },
                    "object": {
                        "key": "test.jpg",
                        "size": 20480,
                        "eTag": "d41d8cd98f00b204e9800998ecf8427e"
                    }
                }
            }
        ]
    }

    context = {}

    # Call the Lambda handler
    response = lambda_handler(event, context)

    # Debugging: Print the response from the handler
    print(f"Lambda response: {response}")

    assert "message" in response
    assert "Combined JSON file updated successfully" in response["message"]
