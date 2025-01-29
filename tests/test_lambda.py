import sys
import os
import json
import pytest
import boto3
from moto import mock_aws
import importlib.util

# Mock environment variables for the test
os.environ['OUTPUT_BUCKET_NAME'] = 'your-output-bucket-name'
os.environ['SQS_QUEUE_URL'] = 'https://sqs.ap-south-1.amazonaws.com/278699821793/human'

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

@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "ap-south-1"

@mock_aws
def test_lambda_handler(aws_credentials):
    """Test the lambda_handler function"""
    
    # Mock SQS queue
    sqs = boto3.client('sqs', region_name='ap-south-1')
    queue_url = sqs.create_queue(QueueName='human')['QueueUrl']
    
    # Mock S3 bucket
    s3 = boto3.client('s3', region_name='ap-south-1')
    s3.create_bucket(Bucket='frames-nht')
    s3.create_bucket(Bucket='your-output-bucket-name')  # Create the output bucket as well
    
    # Upload a mock image to S3
    s3.put_object(
        Bucket='frames-nht',
        Key='abm_video//278699821793_abm_video_1737974384719_e936a59a-7989-4240-9faa-0203483a1d7f[2025-01-27T10:39:50.103364].jpg',
        Body=b'fake-image-data'
    )

    # Mock event structure based on the provided sample
    event = {
        "Records": [
            {
                "messageId": "518ae65b-13c4-4f28-900b-158ba0539706",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps({
                    "Records": [{
                        "eventVersion": "2.1",
                        "eventSource": "aws:s3",
                        "awsRegion": "ap-south-1",
                        "eventTime": "2025-01-27T10:39:50.206Z",
                        "eventName": "ObjectCreated:Put",
                        "userIdentity": {
                            "principalId": "AWS:AROAUBY6NZLQXQJFTD6HC:extract-frame-nht"
                        },
                        "requestParameters": {"sourceIPAddress": "65.1.3.147"},
                        "responseElements": {
                            "x-amz-request-id": "ZXR5FN9N1PQXKX3G",
                            "x-amz-id-2": "ubogeIZalmTLgjHLGCPhfuYj6F4ZvoaNnN/SudnPJsA4IFk8WOw1IemEVwQtlWt6FVmhspm5iGZ204zlEm2Ic3KETkh7zGTj"
                        },
                        "s3": {
                            "s3SchemaVersion": "1.0",
                            "configurationId": "61a33a05-d8bb-4dc0-9c90-c909a90f66e7",
                            "bucket": {
                                "name": "frames-nht",
                                "ownerIdentity": {"principalId": "A1SOGSLXVL48HE"},
                                "arn": "arn:aws:s3:::frames-nht"
                            },
                            "object": {
                                "key": "abm_video//278699821793_abm_video_1737974384719_e936a59a-7989-4240-9faa-0203483a1d7f%5B2025-01-27T10%3A39%3A50.103364%5D.jpg",
                                "size": 18295,
                                "eTag": "9dd068214619420c8523e7a12b7e5fdd",
                                "sequencer": "006797627628DF18BF"
                            }
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
