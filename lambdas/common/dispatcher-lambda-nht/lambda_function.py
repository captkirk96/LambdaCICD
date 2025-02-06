import json
import os

# Initialize the Lambda client
lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    print("Received S3 event:", json.dumps(event))
    
    target_functions = [
        os.environ.get("FALL_DETECTION_FUNCTION_ARN"),
        os.environ.get("FIRE_DETECTION_FUNCTION_ARN"),
        os.environ.get("PERSON_DETECTION_FUNCTION_ARN")
    ]
    
    for function_arn in target_functions:
        if function_arn:
            try:
                response = lambda_client.invoke(
                    FunctionName=function_arn,
                    InvocationType='Event',
                    Payload=json.dumps(event)
                )
                print(f"Successfully invoked {function_arn}: {response['StatusCode']}")
            except Exception as e:
                print(f"Failed to invoke {function_arn}: {str(e)}")
    
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Dispatcher executed successfully"})
    }