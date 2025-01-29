import json
import cv2
import boto3
import tempfile
import os
import time
import requests

# Initialize S3 client
s3_client = boto3.client('s3')

# Load the Haar Cascade car detector
car_detector = cv2.CascadeClassifier("cars.xml")
if car_detector.empty():
    print("DEBUG: Failed to load Haar Cascade file. Check the 'cars.xml' path.")

def download_file_from_s3(bucket_name, key, retries=3, delay=2):
    """Download a file from S3 and save it locally."""
    for attempt in range(retries):
        try:
            print(f"DEBUG: Attempting to download {key} from bucket {bucket_name} (Attempt {attempt + 1})")
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            s3_client.download_file(bucket_name, key, temp_file.name)
            print(f"DEBUG: Successfully downloaded {key} to {temp_file.name}")
            return temp_file
        except Exception as e:
            print(f"DEBUG: Error downloading {key} - {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    raise Exception(f"Failed to download {key} from S3 after {retries} attempts")

def clean_up_temp_file(file):
    try:
        os.unlink(file.name)
        print(f"DEBUG: Temporary file {file.name} deleted")
    except Exception as e:
        print(f"Error deleting temporary file {file.name}: {e}")

def update_detection_status_json(final_bucket, image_key, detection_status_output, detector_name ):
    """
    Updates or creates a combined JSON file with the given human and vehicle statuses for a frame.

    """
    # Extract directory name and form the JSON file name
    directory_path = os.path.dirname(image_key)
    directory_name = os.path.join(directory_path, detector_name + '.json')

    # Check if the combined JSON file exists in the S3 bucket
    try:
        detection_status_file = download_file_from_s3(final_bucket, directory_name)
        with open(detection_status_file.name, 'r') as f:
            detection_status_json = json.load(f)
    except Exception:
        detection_status_json = {}

    # Update or create a new entry for the frame
    frame_id = os.path.basename(image_key).rsplit('.', 1)[0]
    print(f"DEBUG: Updating frame_id: {frame_id}")

    # Update or create a new entry for the frame
    detection_status_json[frame_id] = detection_status_output

    # Save the updated combined JSON to a temporary file
    updated_json_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
    with open(updated_json_file.name, 'w') as f:
        json.dump(detection_status_json, f)

    print(f"Updated {detector_name}.json with {frame_id}: {detection_status_output}")

    return directory_name,updated_json_file

def detect_cars_in_image(image_path):
    """Detect cars in an image using Haar Cascade."""
    try:
        print(f"DEBUG: Loading image from {image_path}")
        img = cv2.imread(image_path)
        if img is None:
            print(f"DEBUG: Failed to load image at {image_path}")
            return False

        print("DEBUG: Converting image to grayscale")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        print("DEBUG: Detecting cars in the image")
        results = car_detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3)
        print(f"DEBUG: Cars detected: {len(results)}")

        return len(results) > 0
    except Exception as e:
        print(f"DEBUG: Error during car detection - {e}")
        return False

def upload_file_to_s3(file_path, bucket_name, key):
    """Upload a file to S3."""
    try:
        print(f"DEBUG: Uploading {file_path} to bucket {bucket_name} with key {key}")
        s3_client.upload_file(file_path, bucket_name, key)
        print(f"DEBUG: Successfully uploaded {key} to {bucket_name}")
    except Exception as e:
        print(f"DEBUG: Error uploading file to S3 - {e}")
        raise


def fetch_image_from_s3(bucket_name, object_key,expiration=3600):
    """
    Generate a pre-signed URL to access the S3 object and fetch the image.
    """
    # Generate the pre-signed URL
    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=expiration
        )
    except Exception as e:
        raise Exception(f"Error generating pre-signed URL: {e}")

    # Fetch the image data from the pre-signed URL
    try:
        response = requests.get(presigned_url)
        if response.status_code == 200:
            print("Successfully downloaded image from S3 bucket")
            return response  # Return the image data
        else:
            raise Exception(f"Failed to fetch image from S3: {response.status_code}")
    except Exception as e:
        raise Exception(f"Error fetching image: {e}")
    
def send_image_to_modal(modal_url, image_data):
    """
    Sends an image to the Modal API for processing and returns the results.
    """
    headers = {'Content-Type': 'application/octet-stream'}
    
    try:
        # Sending the image data to Modal API
        modal_response = requests.post(modal_url, data=image_data, headers=headers)

        # Check if the response is successful
        if modal_response.status_code == 200:
            # Process and return the detection results
            results = modal_response.json()
            print(f"Detection Results: {results}")
            return results
        else:
            # Raise exception if the response is not successful
            print(f"Response Text: {modal_response.text}")
            raise Exception(f"Modal API request failed with status code {modal_response.status_code}")
    except Exception as e:
        # Handle any exceptions that occur during the request
        raise Exception(f"Error during Modal API request: {e}")

def update_combined_json(image_key, human_status, vehicle_status, final_bucket):
    """
    Updates the combined JSON file in the S3 bucket with the given frame information.
    """
    # Extract directory name from the image key to use as the output JSON filename
    directory_path = os.path.dirname(image_key)
    directory_name = os.path.join(directory_path, os.path.basename(directory_path) + '.json')

    # Check if the combined JSON file exists in the final_bucket bucket
    try:
        combined_json_file = download_file_from_s3(final_bucket, directory_name)
        with open(combined_json_file.name, 'r') as f:
            combined_json = json.load(f)
    except Exception as e:
        print(f"Error downloading or reading the combined JSON file: {e}")
        combined_json = {}

    # Update or create a new entry for the frame
    frame_id = os.path.basename(image_key).rsplit('.', 1)[0]
    print(f"DEBUG: Updating frame_id: {frame_id}")
    if frame_id not in combined_json:
        combined_json[frame_id] = []

    # Avoid duplicate entries
    if human_status not in combined_json[frame_id]:
        combined_json[frame_id].append(human_status)

    if vehicle_status not in combined_json[frame_id]:
        combined_json[frame_id].append(vehicle_status)
    # print(combined_json)

    # Save the updated combined JSON to a temporary file
    try:
        updated_json_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        with open(updated_json_file.name, 'w') as f:
            json.dump(combined_json, f)
    except Exception as e:
        print(f"Error saving the updated JSON file: {e}")
        return None, None

    return directory_name, updated_json_file

def clean_up_temp_file(file):
    try:
        os.unlink(file.name)
        print(f"DEBUG: Temporary file {file.name} deleted")
    except Exception as e:
        print(f"Error deleting temporary file {file.name}: {e}")

def lambda_handler(event, context):
    try:
        final_bucket = os.environ['FINAL_OUTPUT_BUCKET']

        bucket_name = event.get("bucket_name")
        image_key = event.get("image_key")

        # Fetch the image data from the pre-signed URL
        response = fetch_image_from_s3(bucket_name, image_key,expiration=3600)

        modal_url = "https://phronetic-ai--vehicle-detector-tracker-detect-and-track.modal.run"
        image_data = response.content
        vehicle_results = send_image_to_modal(modal_url, image_data)
        
        if vehicle_results == []:
            vehicle_status = "No vehicles detected"
        else:
            vehicle_status = vehicle_results

        directory_name, updated_json_file = update_detection_status_json(final_bucket, image_key, vehicle_status, "vehicle_status" )
        # Upload the updated JSON to the "final-output1" bucket
        upload_file_to_s3(updated_json_file.name, final_bucket, directory_name)

        clean_up_temp_file(updated_json_file)

        return {
            "bucket_name": final_bucket,
            "updated_json": directory_name,
            "message": "Combined JSON file updated successfully."
        }

    except Exception as e:
        print(f"DEBUG: Error in Lambda function - {e}")
        return {
            "error": str(e),
            "message": "Error processing the event."
        }
