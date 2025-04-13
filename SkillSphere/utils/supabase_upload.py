import uuid
from supabase import create_client
from django.conf import settings

# Create a global supabase client using the service role key (only for server-side use)
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

def upload_to_supabase(file, folder='uploads', filename=None, content_type='application/octet-stream'):
    """
    Uploads a file to Supabase Storage and returns the public URL.

    :param file: A Django UploadedFile object.
    :param folder: Sub-folder in the bucket, e.g., 'class_thumbnails' or 'profile_images'
    :param filename: An optional filename override; if not provided, use file.name.
    :param content_type: The content type of the file.
    :return: The public URL of the uploaded file.
    :raises Exception: If the upload fails.
    """
    # Read the file content into bytes
    file_bytes = file.read()

    # Use provided filename or the file's original name, then extract the extension
    extension = (filename or file.name).split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{extension}"
    file_path = f"{folder}/{unique_filename}"

    # Attempt the upload with the file content (as bytes)
    upload_response = supabase.storage.from_("media").upload(
        file_path,
        file_bytes,
        {"content-type": content_type}
    )

    # Check if the upload response contains an error by treating it as a dictionary
    error = upload_response.get("error")
    if error:
        raise Exception(f"Upload failed: {error.get('message', 'Unknown error')}")

    # Retrieve the public URL from Supabase
    public_url_response = supabase.storage.from_("media").get_public_url(file_path)
    # Depending on the version of the Supabase Python library, the public URL may be in an attribute or dict key.
    try:
        public_url = public_url_response.publicURL
    except AttributeError:
        public_url = public_url_response.get("publicURL")
    return public_url
