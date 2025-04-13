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

        # Check if upload_response has a 'data' attribute (successful upload)
        if not upload_response or not getattr(upload_response, "data", None):
            raise Exception("Upload failed: No data returned from Supabase.")

        # Get public URL
        public_url_response = supabase.storage.from_("media").get_public_url(file_path)

        # Access public URL (depending on Supabase client version)
        try:
            public_url = public_url_response.publicURL
        except AttributeError:
            public_url = public_url_response.get('publicURL')

        return public_url

    except Exception as e:
        # Raise exception with upload error message
        raise Exception(f"Upload to Supabase failed: {e}")
