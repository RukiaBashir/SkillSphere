import uuid
from supabase import create_client
from django.conf import settings

# Global Supabase client
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def upload_to_supabase(file, folder='uploads', filename=None, content_type='application/octet-stream'):
    """
    Uploads a file to Supabase Storage and returns the public URL.
    """
    # Read the file content into bytes
    file_bytes = file.read()

    # Generate unique filename
    extension = (filename or file.name).split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{extension}"
    file_path = f"{folder}/{unique_filename}"

    try:
        # Upload file content to Supabase Storage
        upload_response = supabase.storage.from_("media").upload(
            file_path,
            file_bytes,
            {"content-type": content_type}
        )

        # If there's an error property, check it
        if hasattr(upload_response, 'error') and upload_response.error:
            raise Exception(f"Upload failed: {upload_response.error.message}")

        # Upload_response is None if success in latest supabase-py
        if upload_response is not None:
            raise Exception("Upload failed: Unexpected response from Supabase.")

        # Get public URL
        public_url_response = supabase.storage.from_("media").get_public_url(file_path)

        # Access public URL
        public_url = getattr(public_url_response, 'publicURL', None)

        if not public_url:
            raise Exception("Failed to retrieve public URL from Supabase.")

        return public_url

    except Exception as e:
        raise Exception(f"Upload to Supabase failed: {e}")
