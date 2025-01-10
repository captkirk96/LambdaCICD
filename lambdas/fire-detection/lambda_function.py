import cv2
import numpy as np
import boto3
import os
import json
import datetime
import tempfile

# Initialize S3 client
s3 = boto3.client('s3')

def check_if_file_exists(bucket_name, key):
    """Check if a file exists in S3."""
    try:
        s3.head_object(Bucket=bucket_name, Key=key)
        print(f"DEBUG: File {key} exists in bucket {bucket_name}")
        return True
    except Exception as e:
        print(f"DEBUG: File {key} does not exist in bucket {bucket_name} - {e}")
        return False
    
def download_file_from_s3(bucket_name, key):
    """Download a file from S3 and save it locally."""
    try:
        print(f"DEBUG: Attempting to download {key} from bucket {bucket_name}")
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        s3.download_file(bucket_name, key, temp_file.name)
        print(f"DEBUG: Successfully downloaded {key} to {temp_file.name}")
        return temp_file
    except Exception as e:
        print(f"DEBUG: Error downloading {key} - {e}")
        raise

def upload_file_to_s3(file_path, bucket_name, key):
    """Upload a file to S3."""
    try:
        print(f"DEBUG: Uploading {file_path} to bucket {bucket_name} with key {key}")
        s3.upload_file(file_path, bucket_name, key)
        print(f"DEBUG: Successfully uploaded {key} to {bucket_name}")
    except Exception as e:
        print(f"DEBUG: Error uploading file to S3 - {e}")
        raise
    
def lambda_handler(event, context):

    # # Initialize S3 client
    # s3 = boto3.client('s3')

    # Define S3 bucket and keys
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    image_key = event['Records'][0]['s3']['object']['key']  # The uploaded image file
    input_video_path = '/tmp/fire.mp4'
    output_json_path = '/tmp/fire_detection_results.json'

    # Get output bucket name from environment variable
    output_bucket_name = os.environ['OUTPUT_BUCKET_NAME']

    # Download Image from S3
    try:
        s3.download_file(bucket_name, image_key, input_video_path)
        print("Image downloaded successfully.")
    except Exception as e:
        print(f"Failed to download image from S3: {e}")
        return {"statusCode": 500, "body": f"Error downloading video: {e}"}
    try:
        # Open the video file
        cap = cv2.VideoCapture(input_video_path)

        # Fire detection details
        fire_detected = False
        total_frames = 0
        fire_frames = 0
        fire_regions = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break  # Break the loop if no more frames

            total_frames += 1

            # Resize for faster processing
            frame = cv2.resize(frame, (640, 360))

            # Convert frame to HSV color space
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # Define fire color range
            lower_fire = np.array([15, 100, 200])  # Lower bound of "fire" color in HSV
            upper_fire = np.array([35, 255, 255])  # Upper bound of "fire" color in HSV

            # Threshold the image to extract fire-like regions
            mask = cv2.inRange(hsv, lower_fire, upper_fire)

            # Apply morphology to reduce noise
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            # Combine fire detection with brightness check
            brightness_mask = cv2.inRange(hsv[:, :, 2], 200, 255)  # Focus on bright regions
            combined_mask = cv2.bitwise_and(mask, brightness_mask)

            # Find contours of the detected fire regions
            contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            frame_fire_detected = False
            frame_fire_regions = []

            for contour in contours:
                if cv2.contourArea(contour) > 1000:  # Minimum area to reduce false positives
                    frame_fire_detected = True
                    x, y, w, h = cv2.boundingRect(contour)
                    frame_fire_regions.append({'x': x, 'y': y, 'width': w, 'height': h})

            if frame_fire_detected:
                fire_detected = True

        # Release resources
        cap.release()

        if fire_detected:
            fire_status = "fire detected"
        else:
            fire_status = "fire not detected"

        # Generate the response
        # timestamp = datetime.datetime.now().isoformat()
        response_data = {

            "fire_status": fire_status
        }

        print(response_data)

        # Extract directory name from JSON key to use as the output JSON filename
        directory_path = os.path.dirname(image_key)
        directory_name = os.path.join(directory_path, os.path.basename(directory_path) + '.json')

        # Check if the combined JSON file exists in the "final-output1" bucket
        try:
            combined_json_file = download_file_from_s3("final-output1", directory_name)
            with open(combined_json_file.name, 'r') as f:
                combined_json = json.load(f)
        except Exception:
            combined_json = {}

        # Update or create a new entry for the frame
        frame_id = os.path.basename(image_key).rsplit('.', 1)[0]
        print(f"frame_id:{frame_id}")
        if frame_id not in combined_json:
            combined_json[frame_id] = []
        combined_json[frame_id].append(fire_status)

        # Save the updated combined JSON to a temporary file
        updated_json_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        with open(updated_json_file.name, 'w') as f:
            json.dump(combined_json, f)

        # Upload the updated JSON to the "final-output1" bucket
        upload_file_to_s3(updated_json_file.name, "final-output1", directory_name)

        # Clean up temporary files
        # os.unlink(json_file.name)
        # os.unlink(image_file.name)
        # os.unlink(updated_json_file.name)
        # print(f"DEBUG: Temporary files deleted")

        return {
            "bucket_name": "final-output1",
            "updated_json": directory_name,
            "message": "Combined JSON file updated successfully."
        }

    except Exception as e:
        print(f"DEBUG: Error in Lambda function - {e}")
        return {
            "error": str(e),
            "message": "Error processing the event."
        }