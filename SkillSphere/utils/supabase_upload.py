import uuid
import boto3
from django.conf import settings

# Create S3 client
s3_client = boto3.client(
    's3',
    endpoint_url=settings.SUPABASE_S3_ENDPOINT_URL,
    aws_access_key_id=settings.SUPABASE_ACCESS_KEY,
    aws_secret_access_key=settings.SUPABASE_SECRET_KEY
)


def upload_to_supabase_s3(file, folder='uploads', filename=None, content_type='application/octet-stream'):
    """
    Uploads a file to Supabase Storage (S3-compatible) and returns its public URL.
    """
    extension = (filename or file.name).split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{extension}"
    key = f"{folder}/{unique_filename}"

    # Upload file
    s3_client.upload_fileobj(
        file,
        settings.SUPABASE_BUCKET,
        key,
        ExtraArgs={"ContentType": content_type, "ACL": "public-read"}  # 'public-read' if your bucket is public
    )

    # Construct public URL manually
    public_url = f"{settings.SUPABASE_S3_ENDPOINT_URL}/{settings.SUPABASE_BUCKET}/{key}"
    return public_url
