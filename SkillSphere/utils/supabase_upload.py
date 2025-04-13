import boto3
from django.conf import settings
import uuid


def upload_to_supabase_s3(file, folder='uploads', filename=None, content_type='application/octet-stream'):
    """
    Upload a file to Supabase Storage via S3-compatible endpoint and return public URL.
    """
    # Use provided filename or generate a unique one
    extension = (filename or file.name).split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{extension}"
    file_path = f"{folder}/{unique_filename}"

    # Initialize boto3 client with Supabase S3 credentials
    s3_client = boto3.client(
        's3',
        endpoint_url=settings.SUPABASE_S3_ENDPOINT,  # your S3 connection endpoint
        aws_access_key_id=settings.SUPABASE_S3_ACCESS_KEY,
        aws_secret_access_key=settings.SUPABASE_S3_SECRET_KEY,
        region_name='us-east-1',  # Supabase S3-compatible defaults to this — unless yours is customized
    )

    # Upload file object (file should be a file-like object opened in 'rb' mode)
    s3_client.put_object(
        Bucket='media',  # your Supabase storage bucket name
        Key=file_path,
        Body=file,
        ContentType=content_type,
        ACL='public-read'  # or adjust if bucket is public
    )

    # Construct public URL
    public_url = f"{settings.SUPABASE_S3_ENDPOINT}/media/{file_path}"
    return public_url
