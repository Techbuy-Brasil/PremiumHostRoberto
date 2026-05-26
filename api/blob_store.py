import json
import os
import urllib.request
import urllib.error


BLOB_URL = os.environ.get("BLOB_API_URL", "")
BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")


def blob_available():
    return bool(BLOB_URL and BLOB_TOKEN)


def blob_read():
    """Read JSON from Vercel Blob. Returns None if unavailable."""
    if not blob_available():
        return None
    try:
        req = urllib.request.Request(BLOB_URL, headers={
            "Authorization": f"Bearer {BLOB_TOKEN}",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def blob_write(data):
    """Write JSON to Vercel Blob. Returns True on success."""
    if not blob_available():
        return False
    try:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            BLOB_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {BLOB_TOKEN}",
                "Content-Type": "application/json",
            },
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def blob_get_key(key: str):
    """Read blob and return a specific top-level key. Returns None if missing."""
    data = blob_read()
    if isinstance(data, dict):
        return data.get(key)
    return None


def blob_set_key(key: str, value):
    """Set a top-level key in the blob without overwriting other keys."""
    if not blob_available():
        return False
    try:
        data = blob_read()
        if not isinstance(data, dict):
            data = {}
        data[key] = value
        return blob_write(data)
    except Exception:
        return False
