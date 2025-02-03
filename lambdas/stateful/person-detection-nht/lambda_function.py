import cv2
import boto3
import json
import os
import requests
import urllib.parse
import pymongo
import datetime
import re

# Initialize S3 client
s3_client = boto3.client('s3')

def fetch_image_from_s3(bucket_name, object_key, expiration=3600):
    """
    Generate a pre-signed URL to access the S3 object and fetch  the image.
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
    return stream_id, frame_id

# MongoDB connection setup
MONGO_URI = "mongodb+srv://aparnajayanv:1TB20dYCWmv1W4CQ@lambdacluster.ovcgx.mongodb.net/"  # MongoDB Atlas connection string
DB_NAME = "lambda_outputs"  # MongoDB database name
COLLECTION_NAME = "combined_output" # collection to store combined lambda outputs
HUMAN_COLLECTION_NAME = "human_detection_output"

# Connect to MongoDB Atlas
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]
combined_collection = db[COLLECTION_NAME]
human_collection = db[HUMAN_COLLECTION_NAME]

def store_output_in_mongo(collection, stream_id, detection_type, frame_id, detection_status):
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
    """
    Process the S3 event payload received via SQS and invoke the next Lambda.
    """
    try:
        # Extract bucket name and object key from the S3 event
        bucket_name = s3_event['bucket']['name']
        object_key = s3_event['object']['key']
        object_key = urllib.parse.unquote(object_key)

        # Fetch the image data from the pre-signed URL
        response = fetch_image_from_s3(bucket_name, object_key, expiration=3600)

        # Send the image data to the Modal web endpoint
        modal_url = "https://phronetic-ai--person-detector-tracker-detect-and-track.modal.run"
        image_data = response.content
        results = send_image_to_modal(modal_url, image_data)

        # Determine the human detection status
        human_status = "No humans detected" if not results else results

        frame_name = os.path.basename(object_key).rsplit('.', 1)[0]

        try:
            stream_id, frame_id = get_frame_stream_id(frame_name)
        except Exception as e:
            stream_id = os.path.dirname(object_key)
            frame_id = frame_name

        store_output_in_mongo(human_collection, stream_id, "human_status", frame_id, human_status) # store data in human collection
        store_output_in_mongo(combined_collection, stream_id, "human_status", frame_id, human_status) # store data in combined collection

        return {
            "mongodb": db,
            "mongodb_combined_collection": combined_collection,
            "mongodb_human_collection" : human_collection,
            "directory_name": stream_id,
            "message": "Output data successfully saved in mongodb"
        }

    except Exception as e:
        print(f"Error processing S3 event: {e}")

def lambda_handler(event, context):
    """
    Lambda handler for processing SQS messages containing S3 events.
    """
    try:
        print(f"DEBUG: Event received: {json.dumps(event)}")

        sqs = boto3.client('sqs')
        
        # Loop through SQS messages
        for record in event.get('Records', []):
            try:
                # Parse the S3 event from the SQS message body
                sqs_message = json.loads(record['body'])
                s3_event = sqs_message.get('Records', [])[0]['s3']
                receipt_handle = record['receiptHandle']  # Get the receipt handle for deleting the message
                queue_url = os.environ.get('SQS_QUEUE_URL')  # SQS queue URL from environment variable

                # Process the S3 event
                process_s3_event(s3_event)

                # After processing the message, delete it from the SQS queue
                if queue_url:
                    sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle
                )
                else:
                    print("DEBUG: SQS_QUEUE_URL environment variable is not set. Skipping message deletion.")

            except Exception as e:
                print(f"Error processing SQS message: {e}")

        return {"statusCode": 200, "message": "Processing completed successfully"}

    except Exception as e:
        print(f"DEBUG: Error in Lambda function - {e}")
        return {"statusCode": 500, "error": str(e), "message": "Error processing the event"}
