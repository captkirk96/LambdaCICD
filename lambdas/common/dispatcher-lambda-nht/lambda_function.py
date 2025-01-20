import boto3
import json

# Initialize the Lambda client
lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    """
    Dispatcher function to invoke other Lambda functions when an S3 event occurs.
    """
    # Log the incoming S3 event
    print("Received S3 event:", json.dumps(event))
    
    # List of target Lambda functions to invoke
    target_functions = [
        "arn:aws:lambda:ap-south-1:278699821793:function:fall-detection-nht",
        "arn:aws:lambda:ap-south-1:278699821793:function:fire-detection-nht",
        "arn:aws:lambda:ap-south-1:278699821793:function:person-detection-nht"
    ]
    
    # Loop through and invoke each Lambda function asynchronously
    for function_arn in target_functions:
        try:
            response = lambda_client.invoke(
                FunctionName=function_arn,
                InvocationType='Event',  # Async invocation
                Payload=json.dumps(event)  # Pass the S3 event as payload
            )
            print(f"Successfully invoked {function_arn}: {response['StatusCode']}")
        except Exception as e:
            print(f"Failed to invoke {function_arn}: {str(e)}")
    
    return {
        "statusCode": 200,
        "body": "Dispatcher executed successfully"
    }
