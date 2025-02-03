import cv2
import boto3
import json
import os
import tempfile
import urllib.parse
import pymongo
import datetime
import json
import re

# Initialize the S3 client
s3 = boto3.client('s3')

def download_file_from_s3(bucket_name, key):
    """Download a file from  S3 and save it locally."""
    try:
        print(f"DEBUG: Attempting  to download {key} from bucket {bucket_name}")
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        s3.download_file(bucket_name, key, temp_file.name)
        print(f"DEBUG: Successfully downloaded {key} to {temp_file.name}")
        return temp_file
    except Exception as e:
        print(f"DEBUG: Error downloading {key} - {e}")
        raise

def clean_up_temp_file(file):
    try:
        os.unlink(file.name)
        print(f"DEBUG: Temporary file {file.name} deleted")
    except Exception as e:
        print(f"Error deleting temporary file {file.name}: {e}")

def detect_fall(input_image_path):
    image = cv2.imread(input_image_path)
    if image is None:
        raise Exception("Failed to load input image.")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    fgbg = cv2.createBackgroundSubtractorMOG2()
    fgmask = fgbg.apply(gray)

    contours, _ = cv2.findContours(fgmask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    fall_detected = False

    if contours:
        areas = [cv2.contourArea(contour) for contour in contours]
        max_area = max(areas, default=0)

        MIN_AREA_THRESHOLD = 500
        if max_area > MIN_AREA_THRESHOLD:
            max_area_index = areas.index(max_area)
            cnt = contours[max_area_index]
            x, y, w, h = cv2.boundingRect(cnt)

            aspect_ratio = h / w if w != 0 else 0
            FALL_ASPECT_RATIO_THRESHOLD = 0.5
            FALL_WIDTH_HEIGHT_THRESHOLD = 1.2

            if aspect_ratio < FALL_ASPECT_RATIO_THRESHOLD and w > FALL_WIDTH_HEIGHT_THRESHOLD * h:
                fall_detected = True
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 0, 255), 2)
            else:
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)

    fall_status = "fall detected" if fall_detected else "fall not detected"
    return fall_status

def get_frame_stream_id(frame_name):
    # Regular expression pattern
    pattern = r"^(\d+)_.*?_(\d+)_"

    # Extract values
    match = re.match(pattern, frame_name)
    if match:
        stream_id = match.group(1)  
        frame_id = match.group(2)   

    print("Stream ID:", stream_id)
    print("Frame ID:", frame_id)
    return stream_id,frame_id

# MongoDB connection setup
MONGO_URI = "mongodb+srv://aparnajayanv:1TB20dYCWmv1W4CQ@lambdacluster.ovcgx.mongodb.net/"  # MongoDB Atlas connection string
DB_NAME = "lambda_outputs"  # MongoDB database name
COLLECTION_NAME = "combined_output"

# Connect to MongoDB Atlas
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]
collection = db[COLLECTION_NAME]

def store_output_in_mongo(stream_id,detection_type,frame_id,detection_status):
    try:
        # Current timestamp
        timestamp = datetime.datetime.utcnow().isoformat()

        # Define the update query and update operation
        query = {"stream_Id": stream_id}
        update = {
            "$set": {
                "updated_at": timestamp,
                f"{detection_type}.{frame_id}": detection_status
            }
        }
        # Perform the upsert operation
        collection.update_one(query, update, upsert=True)
        return f"Successfully updated {detection_type} for {frame_id} in directory {stream_id}"
    
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": str(e),
                    "message": "Failed to update MongoDB",
                }
            ),
        }
    
def process_s3_event(s3_event):
    """Process the S3 event payload."""
    try:
        bucket_name = s3_event['bucket']['name']
        image_key = s3_event['object']['key']
        image_key = urllib.parse.unquote(image_key)
        print(f"DEBUG: Processing file {image_key} from bucket {bucket_name}")

        input_image_path = download_file_from_s3(bucket_name, image_key)
        print("Image downloaded successfully.")
        
        fall_status = detect_fall(input_image_path.name)
        clean_up_temp_file(input_image_path)

        frame_name = os.path.basename(image_key).rsplit('.', 1)[0]

        try:
            stream_id,frame_id = get_frame_stream_id(frame_name)
        except Exception as e:
            stream_id = os.path.dirname(image_key)
            frame_id = frame_name

        store_output_in_mongo(stream_id,"fall_status",frame_id,fall_status)

        return {
            "mongodb":db,
            "mongodb_collection": collection,
            "directory_name": stream_id,
            "message": "Output data successfully saved in mongodb"
        }
    except Exception as e:
        print(f"DEBUG: Error processing S3 event - {e}")
        raise

def lambda_handler(event, context):
    """Lambda handler for processing SQS messages containing S3 events."""
    try:
        print(f"DEBUG: Event received: {json.dumps(event)}")

        # Initialize SQS client
        sqs = boto3.client('sqs')

        for record in event.get('Records', []):
            try:
                # Parse the SQS message
                receipt_handle = record['receiptHandle']
                sqs_message = json.loads(record['body'])
                s3_event = sqs_message.get('Records', [])[0]['s3']

                # Process the S3 event
                process_s3_event(s3_event)

                # Delete the message from the SQS queue after successful processing
                queue_url = os.environ['SQS_QUEUE_URL']  # Ensure SQS queue URL is set in environment variables
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle
                )
                print(f"DEBUG: SQS message with ReceiptHandle {receipt_handle} deleted successfully")

            except Exception as e:
                print(f"Error processing SQS message: {e}")

        return {
            "statusCode": 200,
            "message": "Processing completed successfully"
        }
    except Exception as e:
        print(f"DEBUG: Error in Lambda function - {e}")
        return {
            "statusCode": 500,
            "error": str(e),
            "message": "Error processing the event"
        }
