import os
import sys
import json
import pytest
import boto3
import importlib.util

# Set environment variables
os.environ['OUTPUT_BUCKET_NAME'] = 'final-output-nht'
os.environ["AWS_REGION"] = "ap-south-1"

# Manually load the module using importlib
lambda_module_path = os.path.join(os.path.dirname(__file__), "../lambdas/stateless/fire-detection-nht/lambda_function.py")

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
    local_image_path = "/tmp/fire_sample.jpg"
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
                "messageId": "518ae65b-13c4-4f28-900b-158ba0539706",
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
                                "principalId": "AWS:AROAUBY6NZLQXQJFTD6HC:extract-frame-nht"
                            },
                            "requestParameters": {
                                "sourceIPAddress": "65.1.3.147"
                            },
                            "responseElements": {
                                "x-amz-request-id": "ZXR5FN9N1PQXKX3G",
                                "x-amz-id-2": "ubogeIZalmTLgjHLGCPhfuYj6F4ZvoaNnN/SudnPJsA4IFk8WOw1IemEVwQtlWt6FVmhspm5iGZ204zlEm2Ic3KETkh7zGTj"
                            },
                            "s3": {
                                "s3SchemaVersion": "1.0",
                                "configurationId": "61a33a05-d8bb-4dc0-9c90-c909a90f66e7",
                                "bucket": {
                                    "name": "frames-nht",
                                    "ownerIdentity": {
                                        "principalId": "A1SOGSLXVL48HE"
                                    },
                                    "arn": "arn:aws:s3:::frames-nht"
                                },
                                "object": {
                                    "key": "test.jpg",
                                    "size": 18295,
                                    "eTag": "9dd068214619420c8523e7a12b7e5fdd",
                                    "sequencer": "006797627628DF18BF"
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

    assert "message" in response
    assert response["message"] == "Processing completed successfully"

