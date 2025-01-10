import cv2
import boto3
import tempfile
import os
import json
from PIL import Image
from PIL.ExifTags import TAGS

# Initialize S3 client
s3_client = boto3.client('s3')

# Load the Haar Cascade face detector
face_detector = cv2.CascadeClassifier("face.xml")
if face_detector.empty():
    print("DEBUG: Failed to load Haar Cascade file. Check the 'face.xml' path.")

def download_image_from_s3(bucket_name, key):
    """Download an image from S3 and save it locally."""
    try:
        print(f"DEBUG: Attempting to download {key} from bucket {bucket_name}")
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        s3_client.download_file(bucket_name, key, temp_file.name)
        print(f"DEBUG: Successfully downloaded {key} to {temp_file.name}")
        return temp_file
    except Exception as e:
        print(f"DEBUG: Error downloading {key} - {e}")
        raise

def detect_face_in_image(image_path):
    """Detect faces in an image using Haar Cascade."""
    try:
        print(f"DEBUG: Loading image from {image_path}")
        img = cv2.imread(image_path)
        if img is None:
            print(f"DEBUG: Failed to load image at {image_path}")
            return False

        print("DEBUG: Converting image to grayscale")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        print("DEBUG: Detecting faces in the image")
        results = face_detector.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)
        print(f"DEBUG: Faces detected: {len(results)}")
        
        return len(results) > 0
    except Exception as e:
        print(f"DEBUG: Error during face detection - {e}")
        return False

def extract_image_metadata(image_path):
    """Extract metadata from the image."""
    try:
        print(f"DEBUG: Extracting metadata from image at {image_path}")
        image = Image.open(image_path)
        metadata = image._getexif()
        metadata_dict = {}

        if metadata:
            print("DEBUG: Metadata fields found in the image:")
            for tag_id, value in metadata.items():
                tag = TAGS.get(tag_id, tag_id)
                metadata_dict[tag] = value
                print(f"    {tag}: {value}")  # Print each tag and its value

        created_time = metadata_dict.get("DateTime", "Unknown")
        print(f"DEBUG: Image created time: {created_time}")
        return created_time
    except Exception as e:
        print(f"DEBUG: Error extracting metadata - {e}")
        return "Unknown"


def upload_json_to_s3(bucket_name, key, data):
    """Upload JSON data to an S3 bucket."""
    try:
        print(f"DEBUG: Uploading JSON file to bucket {bucket_name} with key {key}")
        json_data = json.dumps(data)
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=json_data,
            ContentType="application/json"
        )
        print(f"DEBUG: JSON file uploaded successfully to {bucket_name}/{key}")
    except Exception as e:
        print(f"DEBUG: Error uploading JSON file - {e}")
        raise

def lambda_handler(event, context):
    try:
        print("DEBUG: Event received:", event)
        
        # Extract bucket name and object key from the event
        bucket_name = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']

        print(f"DEBUG: Processing file {key} from bucket {bucket_name}")

        # Target bucket for JSON file
        target_bucket_name = "detect-humans-result"

        # Download the image from S3
        temp_file = download_image_from_s3(bucket_name, key)

        # Check for faces in the image
        face_detected = detect_face_in_image(temp_file.name)
        human_status = "Human detected" if face_detected else "No human detected"

        # Extract metadata from the image
        image_created_time = extract_image_metadata(temp_file.name)

        # Clean up the temporary file
        os.unlink(temp_file.name)
        print(f"DEBUG: Temporary file {temp_file.name} deleted")

        # Prepare JSON result
        result = {
            "imagename": key,
            "image_created_time": image_created_time,
            "human_status": human_status
        }

        # Generate JSON key for the target bucket
        json_key = os.path.splitext(key)[0] + ".json"

        # Upload the JSON result to the target bucket
        upload_json_to_s3(target_bucket_name, json_key, result)

        return {
            "message": "Processing completed successful",
            "result": result
        }

    except Exception as e:
        print(f"DEBUG: Error in Lambda function - {e}")
        return {
            "error": str(e),
            "message": "Error processing the event."
        }