import mimetypes
from pathlib import Path


def load_image(image_path: str):
    """Load an image from disk and return a types.Image, or None if path is empty/missing."""
    if not image_path:
        return None
    p = Path(image_path)
    if not p.exists():
        return None
    from google.genai import types  # lazy import — google-genai is optional

    mime, _ = mimetypes.guess_type(str(p))
    return types.Image(
        image_bytes=p.read_bytes(),
        mime_type=mime or "image/png",
    )


def download_from_gcs(gcs_uri: str, local_path: Path, project_id: str) -> None:
    """Download a file from Google Cloud Storage to a local path."""
    from google.cloud import storage as gcs  # lazy import — google-cloud-storage is optional

    uri_body = gcs_uri.replace("gs://", "")
    bucket_name, blob_path = uri_body.split("/", 1)

    storage_client = gcs.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.download_to_filename(str(local_path))
