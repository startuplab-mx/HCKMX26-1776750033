"""
Reset de demo: borra el holdout de Bronze y Silver
para poder repetir la demo desde cero.
Uso: python demo_reset.py
"""

from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")
client = MongoClient(os.getenv("MONGODB_URI"))

HOLDOUT_ID = ObjectId("69ed2ab331962803c5473ae0")

r1 = client["centinela"]["youtube_items"].delete_one({"_id": HOLDOUT_ID})
r2 = client["silver"]["youtube_items"].delete_one({"_id_bronce": HOLDOUT_ID})

print(f"Bronze borrado: {r1.deleted_count}")
print(f"Silver borrado: {r2.deleted_count}")
print("Demo lista para correr.")
