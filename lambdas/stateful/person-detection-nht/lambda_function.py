import cv2
import boto3
import json
import os
import requests
import urllib.parse
import tempfile


# Initialize S3 client
s3_client = boto3.client('s3')

# Load the Haar Cascade face detector
face_detector = cv2.CascadeClassifier("face.xml")

if face_detector.empty():
    print("DEBUG: Failed to load Haar Cascade file. Check the 'face.xml' path.")

def invoke_lambda(function_arn, payload):
    """
    Invoke a Lambda function asynchronously (using 'Event' InvocationType).
    """
    lambda_client = boto3.client('lambda')
    try:
        response = lambda_client.invoke(
            FunctionName=function_arn,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        print(f"Successfully invoked Lambda {function_arn}. Response: {response}")
    except Exception as e:
        print(f"Error invoking Lambda: {e}")

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
        
def upload_file_to_s3(file_path, bucket_name, key):
    """Upload a file to S3."""
    try:
        print(f"DEBUG: Uploading {file_path} to bucket {bucket_name} with key {key}")
        s3_client.upload_file(file_path, bucket_name, key)
        print(f"DEBUG: Successfully uploaded {key} to {bucket_name}")
    except Exception as e:
        print(f"DEBUG: Error uploading file to S3 - {e}")
        raise

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
    
def process_s3_event(s3_event):
    """
    Process the S3 event payload received via SQS and invoke the next Lambda.
    """
    try:
        # Extract bucket name and object key from the S3 event
        bucket_name = s3_event['bucket']['name']
        object_key = s3_event['object']['key']
        object_key = urllib.parse.unquote(object_key)

        output_bucket_name = os.environ['OUTPUT_BUCKET_NAME']

        print(f"DEBUG: Processing file {object_key} from bucket {bucket_name}")

        # Generate a pre-signed URL to access the S3 object
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=3600
        )

        # Fetch the image data from the pre-signed URL
        response = requests.get(presigned_url)
        if response.status_code == 200:
            print("Successfully downloaded image from S3 bucket")
        else:
            raise Exception(f"Failed to fetch image from S3: {response.status_code}")

        # Send the image data to the Modal web endpoint
        modal_url = "https://aparna-j--person-detector-tracker-detect-and-track.modal.run"
        headers = {'Content-Type': 'application/octet-stream'}
        modal_response = requests.post(modal_url, data=response.content, headers=headers)

        if modal_response.status_code == 200:
            # Process the response from Modal
            results = modal_response.json()
            print(f"Detection Results: {results}")
        else:
            print(f"Response Text: {modal_response.text}")
            raise Exception(f"Modal API request failed with status code {modal_response.status_code}")

        # Determine the human detection status
        human_status = "No humans detected" if not results else results

        # Prepare JSON payload for the next Lambda function
        processed_payload = {
            "bucket_name": bucket_name,
            "image_key": object_key,
            "human_status": human_status
        }

        # Invoke the next Lambda function
        invoke_fn_arn = os.environ.get('INVOKE_FUNCTION_ARN')
        if invoke_fn_arn:
            invoke_lambda(invoke_fn_arn, processed_payload)
        else:
            print("DEBUG: INVOKE_FUNCTION_ARN environment variable is not set. Skipping Lambda invocation.")

        directory_name, updated_json_file = update_detection_status_json(output_bucket_name, object_key, human_status, "human_status" )
        # Upload the updated JSON to the "final-output1" bucket
        upload_file_to_s3(updated_json_file.name, output_bucket_name, directory_name)

        clean_up_temp_file(updated_json_file)

    except Exception as e:
        print(f"Error processing S3 event: {e}")

def lambda_handler(event, context):
    """
    Lambda handler for processing SQS messages containing S3 events.
    """
    try:
        print(f"DEBUG: Event received: {json.dumps(event)}")

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
