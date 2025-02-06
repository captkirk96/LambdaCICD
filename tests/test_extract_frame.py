import sys
import json
import pytest
import boto3
from unittest.mock import patch, MagicMock
import cv2
import numpy as np

# Import the lambda function module
lambda_module_path = os.path.join(os.path.dirname(__file__), "../lambdas/common/extract-frame-nht/lambda_function.py")
spec = importlib.util.spec_from_file_location("lambda_function", lambda_module_path)
lambda_module = importlib.util.module_from_spec(spec)
sys.modules["lambda_function"] = lambda_module
spec.loader.exec_module(lambda_module)

# Now, you can use functions from the dynamically imported module
process_video = lambda_module.process_video
lambda_handler = lambda_module.lambda_handler

@pytest.fixture(scope="function")
def mock_s3_client():
    """Mock the S3 client."""
    with patch('boto3.client') as mock:
        yield mock

def test_process_video(mock_s3_client):
    """Test the process_video function."""
    # Mock S3 client methods
    mock_s3 = mock_s3_client.return_value
    mock_s3.download_file = MagicMock()
    mock_s3.put_object = MagicMock()

    # Create a dummy video file
    video_path = '/tmp/test_video.mp4'
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        # Create a dummy video if it doesn't exist
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_path, fourcc, 1.0, (640, 480))
        for _ in range(5):
            frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
            out.write(frame)
        out.release()

    # Call the process_video function
    metrics = process_video('input-bucket', 'test_video.mp4', 'output-bucket')

    # Assertions
    assert len(metrics) > 0
    for metric in metrics:
        assert 'abs_diff' in metric
        assert 'ssim' in metric

def test_lambda_handler(mock_s3_client):
    """Test the lambda_handler function."""
    # Mock S3 client methods
    mock_s3 = mock_s3_client.return_value
    mock_s3.download_file = MagicMock()
    mock_s3.put_object = MagicMock()

    # Mock event structure
    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {
                        "name": "input-bucket"
                    },
                    "object": {
                        "key": "test_video.mp4"
                    }
                }
            }
        ]
    }
    context = {}

    # Call the Lambda handler
    response = lambda_handler(event, context)

    # Assertions
    assert response["statusCode"] == 200
    assert 'frames_processed' in json.loads(response['body'])