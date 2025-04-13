import uuid
from supabase import create_client
from django.conf import settings

# Create a global Supabase client using the service role key (only for server-side use)
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

def upload_to_supabase(file, folder='uploads', filename=None, content_type='application/octet-stream'):
    """
    Uploads a file to Supabase Storage and returns the public URL.

    :param file: A Django UploadedFile object.
    :param folder: Sub-folder in the bucket, e.g., 'class_thumbnails' or 'profile_images'.
    :param filename: Optional override for the filename; if not provided, file.name is used.
    :param content_type: The MIME type of the file.
    :return: The public URL of the uploaded file.
    :raises Exception: If the upload fails.
    """
    # Read the file content into bytes
    file_bytes = file.read()

    # Use provided filename or the file's original name; then extract the extension
    extension = (filename or file.name).split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{extension}"
    file_path = f"{folder}/{unique_filename}"

    # Attempt the upload using the file content (as bytes)
    upload_response = supabase.storage.from_("media").upload(
        file_path,
        file_bytes,
        {"content-type": content_type}
    )

    # Check for an error in the upload response (assuming the response exposes an 'error' attribute)
    if upload_response.error is not None:
        raise Exception(f"Upload failed: {upload_response.error.message}")

    # Retrieve the public URL from Supabase Storage
    public_url_response = supabase.storage.from_("media").get_public_url(file_path)

    # Depending on your Supabase Python library version, access the public URL as an attribute or dictionary key
    try:
        public_url = public_url_response.publicURL
    except AttributeError:
        public_url = public_url_response["publicURL"]

    return public_url
