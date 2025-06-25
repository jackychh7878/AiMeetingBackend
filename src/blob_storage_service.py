import os
from dotenv import load_dotenv
from minio import Minio
from datetime import timedelta
import mimetypes
import socket

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
# server_ip = get_local_ip()
# print(f"MinIO server accessible at: {server_ip}:9000")
#
# # Initialize client
# client = Minio(f"{server_ip}:9000",
#                access_key="minioadmin",
#                secret_key="minioadmin",
#                secure=False)

# Public access via ngrok
ngrok_host = os.getenv("NGROK_HOST")  # <-- use your current ngrok host
client = Minio(f"{ngrok_host}",
               access_key=os.getenv("NGROK_ACCESS_KEY"),
               secret_key=os.getenv("NGROK_SECRET_KEY"),
               secure=True)  # ngrok uses https

def minio_upload_and_share(file_path: str, bucket: str, object_name: str, expiry_hours: int = 1) -> str:
    """
    Uploads a blob from Minio Blob Storage.

    :param file_path: Path to the file to be uploaded.
    :param bucket: Name of the bucket where the file will be uploaded.
    :param object_name: Name of the blob to be uploaded.
    :param expiry_hours: How long should the blob expire.
    :return: The sas url path of the uploaded file.
    """

    # Ensure bucket exists
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)

    # Detect MIME type
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or 'application/octet-stream'

    # Upload
    client.fput_object(bucket, object_name, file_path, content_type=content_type)

    # Generate presigned URL for GET
    url = client.get_presigned_url(
        "GET", bucket, object_name,
        expires=timedelta(hours=expiry_hours)
    )
    return url


def minio_delete_blob(bucket: str, object_name: str):
    """
    Deletes a blob from Azure Blob Storage.

    :param bucket: Bucket of the blob
    :param object_name: Name of the blob to be deleted.
    :return: Boolean indicating whether the deletion was successful.
    """
    try:
        client.remove_object(bucket, object_name)
        print(f"Blob '{object_name}' deleted successfully.")
        return True
    except Exception as e:
        print(f"An error occurred while deleting the blob: {e}")
        return False

def generate_sharing_info(sas_url: str, object_name: str) -> str:
    """
    Generate sharing information for the file
    """
    sharing_info = f"""
=== FILE SHARING INFORMATION ===
File: {object_name}
SAS URL: {sas_url}

To download this file from another computer:
1. Copy the SAS URL above
2. Open a web browser on the other computer
3. Paste the URL and press Enter
4. The file will download automatically

Note: This URL will expire in 1 hour.
"""
    return sharing_info

# if __name__ == '__main__':
    # file_path_link = "C:/Users/JackyChong/Downloads/polyU_CDO_demo.mp4"
    # sas_url = minio_upload_and_share(file_path=file_path_link,
    #                        bucket="test-blob-bucket",
    #                        object_name="test_blob",
    #                        expiry_hours=1)
    #
    # print("=" * 50)
    # print("File uploaded successfully!")
    # print(generate_sharing_info(sas_url, "test_blob"))
    # print("=" * 50)
    # minio_delete_blob(bucket="test-blob-bucket",object_name="test_blob")


