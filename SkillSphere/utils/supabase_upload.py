import uuid
from supabase import create_client
from django.conf import settings

# Global Supabase client
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def upload_to_supabase(file, folder='uploads', filename=None, content_type='application/octet-stream'):
    """
    Uploads a file to Supabase Storage and returns the public URL.
    """
    # Read file content into bytes
    file_bytes = file.read()
    file.seek(0)  # Reset pointer so Django can use it later

    # Use your configured bucket, default to 'media' if not set
    bucket_name = getattr(settings, 'SUPABASE_BUCKET', 'media')

    # Generate unique filename
    extension = (filename or file.name).split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{extension}"
    file_path = f"{folder}/{unique_filename}"

    try:
        # Upload to Supabase Storage
        upload_response = supabase.storage.from_(bucket_name).upload(
            file_path,
            file_bytes,
            {"content-type": content_type}
        )

        # Check for upload error
        if hasattr(upload_response, 'error') and upload_response.error:
            raise Exception(f"Upload failed: {upload_response.error.message}")

        # Construct public URL manually (since get_public_url doesn't work for signed buckets)
        public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{file_path}"

        return public_url

    except Exception as e:
        raise Exception(f"Upload to Supabase failed: {e}")
