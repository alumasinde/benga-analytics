import os
from dotenv import load_dotenv
load_dotenv()
def get_settings():
    return {"environment":os.getenv("FLASK_ENV","development"),"secret_key":os.getenv("SECRET_KEY","development-only-change-me"),"max_content_length":int(os.getenv("MAX_CONTENT_LENGTH","104857600")),"upload_folder":os.getenv("UPLOAD_FOLDER","./uploads")}
