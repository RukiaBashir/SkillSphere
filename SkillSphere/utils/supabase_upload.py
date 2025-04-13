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

    # Generate unique filename
    extension = (filename or file.name).split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{extension}"
    file_path = f"{folder}/{unique_filename}"

    try:
        # Upload file content to Supabase Storage

        upload_response = supabase.storage.from_("public").upload(
            file_path,
            file_bytes,
            {"content-type": content_type}
        )

        # Check for an error in the response
        if hasattr(upload_response, 'error') and upload_response.error:
            raise Exception(f"Upload failed: {upload_response.error.message}")

        # Get public URL
        public_url_response = supabase.storage.from_("media").create_signed_url(file_path,
                                                                                expires_in=3600 * 24 * 7)  # 7 days expiry

        # Safely extract the public URL
        if hasattr(public_url_response, 'publicURL') and public_url_response.publicURL:
            public_url = public_url_response.publicURL
            print(public_url)
        elif isinstance(public_url_response, dict) and 'publicURL' in public_url_response:
            public_url = public_url_response['signedURL']
        else:
            # Construct it manually if response didn't give it
            public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/media/{file_path}"

        return public_url

    except Exception as e:
        raise Exception(f"Upload to Supabase failed: {e}")
