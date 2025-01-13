import cv2
import boto3
import datetime
import json
import os
import tempfile


# Initialize the S3 client
s3 = boto3.client('s3')

def check_if_file_exists(bucket_name, key):
    """Check if a file exists in S3."""
    try:
        s3.head_object(Bucket=bucket_name, Key=key)
        print(f"DEBUG: File {key} exists in bucket {bucket_name}")
        return True
    except Exception as e:
        print(f"DEBUG: File {key} does not exist in bucket {bucket_name}")
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
    try:

        # Extract S3 bucket name and object key from the event
        bucket_name = event['Records'][0]['s3']['bucket']['name']
        image_key = event['Records'][0]['s3']['object']['key']  # The uploaded image file

        # Get output bucket name from environment variable
        output_bucket_name = os.environ['OUTPUT_BUCKET_NAME']

        # Temporary file paths in Lambda's /tmp directory
        input_image_path = '/tmp/input_image.jpeg'
        json_response_path = '/tmp/response.json'

        # Download the image from S3
        try:
            s3.download_file(bucket_name, image_key, input_image_path)
            print("Image downloaded successfully.")
        except Exception as e:
            print(f"Failed to download image from S3 bucket: {e}")
            return {"statusCode": 500, "body": f"Error downloading image: {e}"}

        # Load the image for processing
        try:
            image = cv2.imread(input_image_path)
            if image is None:
                raise Exception("Failed to load input image.")

            # Convert image to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Initialize background subtractor
            fgbg = cv2.createBackgroundSubtractorMOG2()
            fgmask = fgbg.apply(gray)

            # Find contours
            contours, _ = cv2.findContours(fgmask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            fall_detected = False  # Flag to track fall detection

            if contours:
                # List to hold areas
                areas = [cv2.contourArea(contour) for contour in contours]
                max_area = max(areas, default=0)

                # Set a minimum area threshold to filter out small objects or noise
                MIN_AREA_THRESHOLD = 500  # Adjust this based on your specific use case

                if max_area > MIN_AREA_THRESHOLD:
                    max_area_index = areas.index(max_area)
                    cnt = contours[max_area_index]

                    # Calculate bounding box
                    x, y, w, h = cv2.boundingRect(cnt)

                    # Calculate aspect ratio
                    aspect_ratio = h / w if w != 0 else 0  # Avoid division by zero

                    # Define thresholds for aspect ratio and height-width relationship
                    FALL_ASPECT_RATIO_THRESHOLD = 0.5  # Threshold for "fallen" aspect ratio
                    FALL_WIDTH_HEIGHT_THRESHOLD = 1.2  # Width should be at least 1.2 times the height

                    # Check for fall condition using aspect ratio and width-height threshold
                    if aspect_ratio < FALL_ASPECT_RATIO_THRESHOLD and w > FALL_WIDTH_HEIGHT_THRESHOLD * h:
                        fall_detected = True
                        cv2.rectangle(image, (x, y), (x + w, y + h), (0, 0, 255), 2)  # Red rectangle for fall
                    else:
                        cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Green rectangle for no fall


            if fall_detected:
                fall_status = "fall detected"
            else:
                fall_status = "fall not detected"
            
            # Create the JSON response
            # timestamp = datetime.datetime.now().isoformat()

            response_data = {

                "fall_status": fall_status
            }

            print(response_data)

            # Extract directory name from JSON key to use as the output JSON filename
            directory_path = os.path.dirname(image_key)
            directory_name = os.path.join(directory_path, os.path.basename(directory_path) + '.json')

            # Check if the combined JSON file exists in the "final-output1" bucket
            try:
                combined_json_file = download_file_from_s3(output_bucket_name, directory_name)
                with open(combined_json_file.name, 'r') as f:
                    combined_json = json.load(f)
            except Exception:
                combined_json = {}

            # Update or create a new entry for the frame
            frame_id = os.path.basename(image_key).rsplit('.', 1)[0]
            print(f"frame_id:{frame_id}")
            if frame_id not in combined_json:
                combined_json[frame_id] = []
            combined_json[frame_id].append(fall_status)

            # Save the updated combined JSON to a temporary file
            updated_json_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
            with open(updated_json_file.name, 'w') as f:
                json.dump(combined_json, f)

            # Upload the updated JSON to the "final-output1" bucket
            upload_file_to_s3(updated_json_file.name, output_bucket_name, directory_name)

            # Clean up temporary files
            # os.unlink(json_file.name)
            # os.unlink(image_file.name)
            # os.unlink(updated_json_file.name)
            # print(f"DEBUG: Temporary files deleted")

            return {
                "bucket_name": output_bucket_name,
                "updated_json": directory_name,
                "message": "Combined JSON file updated successfully"
            }

        except Exception as e:
            print(f"DEBUG: Error in Lambda function - {e}")
            return {
                "error": str(e),
                "message": "Error processing the event."
            }

        # except Exception as e:
        #     print(f"Error processing image: {e}")
        #     return {"statusCode": 500, "body": f"Error processing image: {e}"}

    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"An error occurred: {str(e)}"
        }

