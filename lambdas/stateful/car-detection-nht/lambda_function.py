import json
import cv2
import boto3
import os
import requests
import pymongo
import datetime
import urllib.parse
import re

# Initialize S3 client
s3_client = boto3.client('s3')

def fetch_image_from_s3(bucket_name, object_key, expiration=3600):
    """
    Generate a pre-signed URL to access the S3 object and fetch the image.
    """
    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=expiration
        )
    except Exception as e:
        raise Exception(f"Error generating pre-signed URL: {e}")

    try:
        response = requests.get(presigned_url)
        if response.status_code == 200:
            print("Successfully downloaded image from S3 bucket")
            return response
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
        modal_response = requests.post(modal_url, data=image_data, headers=headers)
        if modal_response.status_code == 200:
            results = modal_response.json()
            print(f"Detection Results: {results}")
            return results
        else:
            print(f"Response Text: {modal_response.text}")
            raise Exception(f"Modal API request failed with status code {modal_response.status_code}")
    except Exception as e:
        raise Exception(f"Error during Modal API request: {e}")

def get_frame_stream_id(frame_name):
    pattern = r"^(\d+)_.*?_(\d+)_"
    match = re.match(pattern, frame_name)
    if match:
        stream_id = match.group(1)  
        frame_id = match.group(2)   
    print("Stream ID:", stream_id)
    print("Frame ID:", frame_id)
    return stream_id, frame_id

# MongoDB connection setup
MONGO_URI = "mongodb+srv://aparnajayanv:1TB20dYCWmv1W4CQ@lambdacluster.ovcgx.mongodb.net/"
DB_NAME = "lambda_outputs"
COLLECTION_NAME = "combined_output"
VEHICLE_COLLECTION_NAME = "vehicle_detection_output"

mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]
combined_collection = db[COLLECTION_NAME]
vehicle_collection = db[VEHICLE_COLLECTION_NAME]

def store_output_in_mongo(collection, stream_id, detection_type, frame_id, detection_status):
    try:
        timestamp = datetime.datetime.utcnow().isoformat()
        query = {"stream_Id": stream_id}
        update = {
            "$set": {
                "updated_at": timestamp,
                f"{detection_type}.{frame_id}": detection_status
            }
        }
        collection.update_one(query, update, upsert=True)
        return f"Successfully updated {detection_type} for {frame_id} in directory {stream_id}"
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e),
                "message": "Failed to update MongoDB",
            }),
        }

def process_s3_event(s3_event):
    try:
        bucket_name = s3_event['bucket']['name']
        image_key = s3_event['object']['key']
        image_key = urllib.parse.unquote(image_key)

        response = fetch_image_from_s3(bucket_name, image_key, expiration=3600)

        modal_url = "https://phronetic-ai--vehicle-detector-tracker-detect-and-track.modal.run"
        image_data = response.content
        vehicle_results = send_image_to_modal(modal_url, image_data)
        
        vehicle_status = "No vehicles detected" if vehicle_results == [] else vehicle_results

        frame_name = os.path.basename(image_key).rsplit('.', 1)[0]

        try:
            stream_id, frame_id = get_frame_stream_id(frame_name)
        except Exception as e:
            stream_id = os.path.dirname(image_key)
            frame_id = frame_name
            print(e)

        store_output_in_mongo(vehicle_collection, stream_id, "vehicle_status", frame_id, vehicle_status)
        store_output_in_mongo(combined_collection, stream_id, "vehicle_status", frame_id, vehicle_status)

        return {
            "mongodb": db,
            "mongodb_combined_collection": combined_collection,
            "mongodb_vehicle_collection": vehicle_collection,
            "directory_name": stream_id,
            "message": "Output data successfully saved in mongodb"
        }
    except Exception as e:
        print(f"DEBUG: Error in Lambda function - {e}")
        return {
            "error": str(e),
            "message": "Error processing the event."
        }

def lambda_handler(event, context):
    try:
        print(f"DEBUG: Event received: {json.dumps(event)}")
        sqs = boto3.client('sqs')
        for record in event.get('Records', []):
            try:
                sqs_message = json.loads(record['body'])
                s3_event = sqs_message.get('Records', [])[0]['s3']
                receipt_handle = record['receiptHandle']
                queue_url = os.environ.get('SQS_QUEUE_URL')
                process_s3_event(s3_event)
                if queue_url:
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
                else:
                    print("DEBUG: SQS_QUEUE_URL environment variable is not set. Skipping message deletion.")
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
