import json
import cv2
import boto3
import tempfile
import os

# Initialize S3 client
s3_client = boto3.client('s3')

# Load the Haar Cascade car detector
car_detector = cv2.CascadeClassifier("cars.xml")
if car_detector.empty():
    print("DEBUG: Failed to load Haar Cascade file. Check the 'cars.xml' path.")

def download_file_from_s3(bucket_name, key):
    """Download a file from S3 and save it locally."""
    try:
        print(f"DEBUG: Attempting to download {key} from bucket {bucket_name}")
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        s3_client.download_file(bucket_name, key, temp_file.name)
        print(f"DEBUG: Successfully downloaded {key} to {temp_file.name}")
        return temp_file
    except Exception as e:
        print(f"DEBUG: Error downloading {key} - {e}")
        raise

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

def lambda_handler(event, context):
    try:
        print("DEBUG: Event received:", event)

        # Extract bucket name and object key from the event
        bucket_name = event['Records'][0]['s3']['bucket']['name']
        json_key = event['Records'][0]['s3']['object']['key']

        print(f"DEBUG: Processing JSON file {json_key} from bucket {bucket_name}")

        # Download the JSON file from S3
        json_file = download_file_from_s3(bucket_name, json_key)

        # Load the JSON content
        with open(json_file.name, 'r') as f:
            data = json.load(f)

        # Extract "human_status" from the received JSON
        human_status = data.get("human_status", "Unknown")

        # Derive the image file key
        image_key = json_key.rsplit('.', 1)[0] + ".jpg"
        print(f"DEBUG: Corresponding image file is {image_key}")

        # Download the image file from the "detect-humans" bucket
        image_file = download_file_from_s3("frames-nht", image_key)

        # Check for cars in the image
        car_status = "Vehicle Detected" if detect_cars_in_image(image_file.name) else "No Vehicle Detected"

        # Extract directory name from JSON key to use as the output JSON filename
        directory_path = os.path.dirname(json_key)
        directory_name = os.path.join(directory_path, os.path.basename(directory_path) + '.json')

        # Check if the combined JSON file exists in the "final-output1" bucket
        try:
            combined_json_file = download_file_from_s3("final-output-nht", directory_name)
            with open(combined_json_file.name, 'r') as f:
                combined_json = json.load(f)
        except Exception:
            combined_json = {}

        # Update or create a new entry for the frame
        frame_id = os.path.basename(json_key).rsplit('.', 1)[0]
        if frame_id not in combined_json:
            combined_json[frame_id] = []
        combined_json[frame_id].append(human_status)
        combined_json[frame_id].append(car_status)

        # Save the updated combined JSON to a temporary file
        updated_json_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        with open(updated_json_file.name, 'w') as f:
            json.dump(combined_json, f)

        # Upload the updated JSON to the "final-output1" bucket
        upload_file_to_s3(updated_json_file.name, "final-output-nht", directory_name)

        # Clean up temporary files
        os.unlink(json_file.name)
        os.unlink(image_file.name)
        os.unlink(updated_json_file.name)
        print(f"DEBUG: Temporary files deleted")

        return {
            "bucket_name": "final-output-nht",
            "updated_json": directory_name,
            "message": "Combined JSON file updated successfully."
        }

    except Exception as e:
        print(f"DEBUG: Error in Lambda function - {e}")
        return {
            "error": str(e),
            "message": "Error processing the event."
        }