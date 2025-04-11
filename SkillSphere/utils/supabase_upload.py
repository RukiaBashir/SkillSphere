import uuid

from supabase import create_client
from django.conf import settings

from SkillSphere.settings import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def upload_to_supabase(file, folder='uploads', content_type='application/octet-stream'):
    """
    Uploads a file to a specific folder in Supabase Storage and returns the public URL.
    :param file: Django UploadedFile object
    :param folder: Sub-folder like 'class_thumbnails' or 'profile_images'
    :return: public URL of uploaded file
    """
    _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    extension = file.name.split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{extension}"
    file_path = f"{folder}/{unique_filename}"

    _supabase.storage.from_('media').upload(file_path, file, {
        "content-type": content_type
    })

    public_url = _supabase.storage.from_('media').get_public_url(file_path)
    return public_url
