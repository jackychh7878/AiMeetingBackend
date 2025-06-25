import os
from dotenv import load_dotenv
from minio import Minio
from datetime import timedelta
import mimetypes
import socket
from enum import Enum
from src.enums import NgrokMode

# Load environment variables
load_dotenv()

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Connect to a remote address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "localhost"


# Get the server's IP address
server_ip = get_local_ip()
print(f"MinIO server accessible at: {server_ip}:9000")

# Initialize client
client = Minio(f"{server_ip}:9000",
               access_key=os.getenv("NGROK_ACCESS_KEY"),
               secret_key=os.getenv("NGROK_SECRET_KEY"),
               secure=False)

# Check if the minio blob storage is public access, or only local access
NGROK_PUBLIC_MODE = os.getenv("NGROK_PUBLIC_MODE")
if NGROK_PUBLIC_MODE == NgrokMode.PUBLIC.value:
    # Public access via ngrok
    ngrok_host = os.getenv("NGROK_HOST")  # <-- use your current ngrok host
    client = Minio(f"{ngrok_host}",
                   access_key=os.getenv("NGROK_ACCESS_KEY"),
                   secret_key=os.getenv("NGROK_SECRET_KEY"),
                   secure=True)  # ngrok uses https

def minio_upload_and_share(file_path: str, bucket: str, blob_name: str, expiry_date: timedelta = timedelta(hours=1)) -> str:
    """
    Uploads a blob from Minio Blob Storage.

    :param file_path: Path to the file to be uploaded.
    :param bucket: Name of the bucket where the file will be uploaded.
    :param blob_name: Name of the blob to be uploaded.
    :param expiry_date: How long should the blob expire.
    :return: The sas url path of the uploaded file.
    """

    # Ensure bucket exists
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)

    # Detect MIME type
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or 'application/octet-stream'

    # Upload
    client.fput_object(bucket, blob_name, file_path, content_type=content_type)

    # Generate presigned URL for GET
    url = client.get_presigned_url(
        "GET", bucket, blob_name,
        expires=expiry_date
    )
    return url


def minio_delete_blob(bucket: str, blob_name: str):
    """
    Deletes a blob from Azure Blob Storage.

    :param bucket: Bucket of the blob
    :param blob_name: Name of the blob to be deleted.
    :return: Boolean indicating whether the deletion was successful.
    """
    try:
        client.remove_object(bucket, blob_name)
        print(f"Blob '{blob_name}' deleted successfully.")
        return True
    except Exception as e:
        print(f"An error occurred while deleting the blob: {e}")
        return False

def generate_sharing_info(sas_url: str, blob_name: str, expiry_date: timedelta) -> str:
    """
    Generate sharing information for the file
    """
    # Convert timedelta to human-readable format
    if expiry_date.days > 0:
        expiry_text = f"{expiry_date.days} day{'s' if expiry_date.days != 1 else ''}"
    elif expiry_date.seconds >= 3600:
        hours = expiry_date.seconds // 3600
        expiry_text = f"{hours} hour{'s' if hours != 1 else ''}"
    elif expiry_date.seconds >= 60:
        minutes = expiry_date.seconds // 60
        expiry_text = f"{minutes} minute{'s' if minutes != 1 else ''}"
    else:
        expiry_text = f"{expiry_date.seconds} second{'s' if expiry_date.seconds != 1 else ''}"
    
    sharing_info = f"""
=== FILE SHARING INFORMATION ===
File: {blob_name}
SAS URL: {sas_url}

To download this file from another computer:
1. Copy the SAS URL above
2. Open a web browser on the other computer
3. Paste the URL and press Enter
4. The file will download automatically

Note: This URL will expire in {expiry_text}.
"""
    return sharing_info

# if __name__ == '__main__':
#     file_path_link = "C:/Users/JackyChong/Downloads/polyU_CDO_demo.mp4"
#     sas_url = minio_upload_and_share(file_path=file_path_link,
#                                      bucket="test-blob-bucket",
#                                      blob_name="test_blob",
#                                      expiry_date=timedelta(hours=1))
#
#     print("=" * 50)
#     print("File uploaded successfully!")
#     print(generate_sharing_info(sas_url, "test_blob", timedelta(hours=1)))
#     print("=" * 50)
#     minio_delete_blob(bucket="test-blob-bucket",object_name="test_blob")


