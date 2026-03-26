import firebase_admin
from firebase_admin import credentials

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

cred = credentials.Certificate(os.path.join(BASE_DIR, "firebase-key.json"))

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        "storageBucket": "desd-6af1a.appspot.com"
    })