import os
import requests

REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

def db_set(user_id, key, value):
    """Stores a file_id for a specific user and filename"""
    full_key = f"user:{user_id}:file:{key}"
    url = f"{REDIS_URL}/set/{full_key}/{value}"
    headers = {"Authorization": f"Bearer {REDIS_TOKEN}"}
    requests.get(url, headers=headers)

def db_get(user_id, key):
    """Retrieves a file_id by filename"""
    full_key = f"user:{user_id}:file:{key}"
    url = f"{REDIS_URL}/get/{full_key}"
    headers = {"Authorization": f"Bearer {REDIS_TOKEN}"}
    res = requests.get(url, headers=headers).json()
    return res.get("result")

def db_list(user_id):
    """Lists all filenames stored by the user"""
    pattern = f"user:{user_id}:file:*"
    url = f"{REDIS_URL}/keys/{pattern}"
    headers = {"Authorization": f"Bearer {REDIS_TOKEN}"}
    res = requests.get(url, headers=headers).json()
    keys = res.get("result", [])
    # Strip the prefix to get clean filenames
    return [k.split(":")[-1] for k in keys]

def db_delete(user_id, key):
    """Deletes a stored file reference"""
    full_key = f"user:{user_id}:file:{key}"
    url = f"{REDIS_URL}/del/{full_key}"
    headers = {"Authorization": f"Bearer {REDIS_TOKEN}"}
    requests.get(url, headers=headers)
