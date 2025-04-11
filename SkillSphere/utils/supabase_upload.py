from supabase import create_client
from django.conf import settings

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def upload_to_supabase(file, filename):
    path = f"{filename}"
    try:
        # Upload to the bucket
        supabase.storage.from_(settings.SUPABASE_BUCKET).upload(path, file, {"cacheControl": "3600", "upsert": True})
        # Get the public URL
        return supabase.storage.from_(settings.SUPABASE_BUCKET).get_public_url(path)
    except Exception as e:
        print("Upload error:", e)
        return None
