import cv2
import json
import boto3
import os
import numpy as np

# Initialize S3 client
s3_client = boto3.client('s3')

def calculate_mad(frame1, frame2):
    """Calculate Mean Absolute Difference (MAD) between two frames."""
    return np.mean(np.abs(frame1 - frame2))

def calculate_ssim(frame1, frame2):
    """Calculate Structural Similarity Index (SSIM) between two frames using cv2."""
    # Convert frames to grayscale using cv2
    gray_frame1 = cv2.cvtColor(frame1, cv2.COLOR_RGB2GRAY)
    gray_frame2 = cv2.cvtColor(frame2, cv2.COLOR_RGB2GRAY)
    
    # Use OpenCV's SSIM calculation (or equivalent comparison method)
    # We will use the normalized cross-correlation method as an approximation
    # Compute the correlation coefficient using cv2.matchTemplate (roughly similar to SSIM)
    result = cv2.matchTemplate(gray_frame1, gray_frame2, cv2.TM_CCOEFF_NORMED)
    return result[0][0]  # This gives the similarity score

def compare_frames(frame1, frame2):
    """
    Calculate and return metrics between two frames:
    - Mean Absolute Difference (MAD)
    - Structural Similarity Index (SSIM)
    """
    # Ensure both frames have 3 channels (RGB)
    if frame1.shape[-1] > 3:
        frame1 = frame1[:, :, :3]
    if frame2.shape[-1] > 3:
        frame2 = frame2[:, :, :3]

    if frame1.shape != frame2.shape:
        frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))

    mad = calculate_mad(frame1, frame2)
    ssim_value = calculate_ssim(frame1, frame2)

    return {
        "abs_diff": float(mad),
        "ssim": float(ssim_value)
    }

def upload_frame_to_s3(frame, bucket, frame_count, video_file_name):
    """
    Convert and upload a frame directly to S3. 
    Creates a folder based on the video file name.
    """
    # Extract base name (without extension) from the video file name
    folder_name = os.path.splitext(video_file_name)[0]

    # Convert frame to BGR and encode as JPEG
    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    _, buffer = cv2.imencode('.jpg', frame_bgr)

    # Upload the frame to S3 using the folder name
    s3_client.put_object(
        Bucket=bucket,
        Key=f"{folder_name}/frame_{frame_count:04d}.jpg",
        Body=buffer.tobytes(),
        ContentType='image/jpeg'
    )



def process_video(input_bucket, input_key, output_bucket):
    """
    Process video frame by frame and calculate metrics between consecutive frames.

    Args:
        input_bucket: S3 bucket containing input video
        input_key: S3 key of input video
        output_bucket: S3 bucket for output frames and metrics
    """
    # Extract filename from the input_key
    file_name = input_key.split('/')[-1]
    video_path = f'/tmp/{file_name}'
    
    # Download video from S3
    s3_client.download_file(input_bucket, input_key, video_path)

    cap = cv2.VideoCapture(video_path)
    metrics_list = []
    frame_count = 0
    previous_frame = None

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if previous_frame is None:
            previous_frame = frame
            upload_frame_to_s3(frame, output_bucket, frame_count, file_name)
            frame_count += 1
            continue

        metrics = compare_frames(previous_frame, frame)
        metrics['frame_number'] = frame_count

        if metrics['abs_diff'] >= 50 or metrics['ssim'] <= 0.95:
            upload_frame_to_s3(frame, output_bucket, frame_count, file_name)

        metrics_list.append(metrics)
        previous_frame = frame
        frame_count += 1

    cap.release()
    os.remove(video_path)

    return metrics_list


def lambda_handler(event, context):
    """
    AWS Lambda handler function.
    """
    try:
        # Extract the source bucket and object key from the event
        record = event['Records'][0]
        input_bucket = record['s3']['bucket']['name']
        input_key = record['s3']['object']['key']
        
        # Define a fixed output bucket
        output_bucket = "detect-humans"
        
        # Process the video
        metrics = process_video(input_bucket, input_key, output_bucket)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Video processing completed',
                'frames_processed': len(metrics)
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
