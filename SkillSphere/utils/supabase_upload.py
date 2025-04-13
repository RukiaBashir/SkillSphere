import uuid
from supabase import create_client
from django.conf import settings


def upload_to_supabase(file, folder='uploads', filename=None, content_type='application/octet-stream'):
    """
    Uploads a file to Supabase Storage and returns its public URL.

    :param file: A Django UploadedFile object or a file-like object.
    :param folder: The folder in the Supabase bucket where the file will be stored.
    :param filename: Optionally override the original filename.
    :param content_type: MIME type of the file.
    :return: The public URL of the uploaded file.
    """
    # Create a Supabase client using the service role key
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

    # Use the provided filename or generate a unique filename based on the file name and a UUID.
    extension = (filename or file.name).split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{extension}"
    file_path = f"{folder}/{unique_filename}"

    # Upload the file. Note: the file must be a file-like object in binary mode.
    response = supabase.storage.from_(settings.SUPABASE_BUCKET).upload(file_path, file, {
        "content-type": content_type
    })

    if response.get("error"):
        raise Exception(response["error"]["message"])

    # Get the public URL from Supabase Storage.
    public_url = supabase.storage.from_(settings.SUPABASE_BUCKET).get_public_url(file_path)
    return public_url
