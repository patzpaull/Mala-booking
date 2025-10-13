# app/services/storage.py

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.client import Config
import io
import logging
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException
from ..config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """
    Service for managing file uploads to DigitalOcean Spaces (S3-compatible)
    """

    def __init__(self):
        """Initialize the S3 client for DigitalOcean Spaces"""
        try:
            self.s3_client = boto3.client(
                's3',
                region_name=settings.do_spaces_region,
                endpoint_url=settings.do_spaces_endpoint,
                aws_access_key_id=settings.do_spaces_access_key,
                aws_secret_access_key=settings.do_spaces_secret_key,
                config=Config(signature_version='s3v4')
            )
            self.bucket_name = settings.do_spaces_bucket
            self.cdn_endpoint = settings.do_spaces_cdn_endpoint or settings.do_spaces_endpoint.replace(
                'digitaloceanspaces.com', 'cdn.digitaloceanspaces.com'
            )
            logger.info(f"Storage service initialized for bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize storage service: {e}")
            raise

    def _get_content_type(self, filename: str) -> str:
        """Determine content type based on file extension"""
        ext = filename.lower().split('.')[-1]
        content_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'svg': 'image/svg+xml'
        }
        return content_types.get(ext, 'application/octet-stream')

    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename"""
        return filename.lower().split('.')[-1] if '.' in filename else 'jpg'

    async def upload_avatar(
        self,
        file: UploadFile,
        keycloak_id: str,
        user_type: str
    ) -> str:
        """
        Upload a user avatar to Spaces

        Args:
            file: The uploaded file
            keycloak_id: User's Keycloak ID
            user_type: User type (CUSTOMER, VENDOR, ADMIN, FREELANCE)

        Returns:
            Public URL of the uploaded file
        """
        try:
            # Get file extension
            ext = self._get_file_extension(file.filename)

            # Build S3 key
            s3_key = f"marketplace/avatars/{user_type}/{keycloak_id}/avatar.{ext}"

            # Read file content
            file_content = await file.read()
            file_obj = io.BytesIO(file_content)

            # Upload to Spaces
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ACL': 'public-read',
                    'ContentType': self._get_content_type(file.filename),
                    'CacheControl': 'max-age=31536000'  # 1 year cache
                }
            )

            # Generate public URL (use CDN if available)
            if self.cdn_endpoint:
                url = f"{self.cdn_endpoint}/{s3_key}"
            else:
                url = f"{settings.do_spaces_endpoint}/{self.bucket_name}/{s3_key}"

            logger.info(f"Avatar uploaded successfully for {keycloak_id}: {url}")
            return url

        except NoCredentialsError:
            logger.error("Credentials not available for Spaces")
            raise HTTPException(status_code=500, detail="Storage credentials not configured")
        except ClientError as e:
            logger.error(f"Error uploading to Spaces: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during upload: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload file")
        finally:
            # Reset file pointer
            await file.seek(0)

    async def delete_avatar(
        self,
        keycloak_id: str,
        user_type: str,
        current_url: Optional[str] = None
    ) -> bool:
        """
        Delete a user's avatar from Spaces

        Args:
            keycloak_id: User's Keycloak ID
            user_type: User type (CUSTOMER, VENDOR, ADMIN, FREELANCE)
            current_url: Current avatar URL (optional, for extracting extension)

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Try to determine extension from current URL or try common extensions
            extensions = ['jpg', 'jpeg', 'png', 'webp', 'gif']

            if current_url:
                # Extract extension from URL
                ext = current_url.split('.')[-1].split('?')[0].lower()
                if ext in extensions:
                    extensions = [ext]  # Try this extension first

            deleted = False
            for ext in extensions:
                s3_key = f"marketplace/avatars/{user_type}/{keycloak_id}/avatar.{ext}"
                try:
                    self.s3_client.delete_object(
                        Bucket=self.bucket_name,
                        Key=s3_key
                    )
                    logger.info(f"Avatar deleted successfully: {s3_key}")
                    deleted = True
                    break  # Stop after first successful deletion
                except ClientError as e:
                    if e.response['Error']['Code'] != 'NoSuchKey':
                        logger.error(f"Error deleting {s3_key}: {e}")
                    continue

            return deleted

        except Exception as e:
            logger.error(f"Unexpected error during avatar deletion: {e}")
            return False

    async def upload_salon_image(
        self,
        file: UploadFile,
        salon_id: int,
        image_type: str = "cover"
    ) -> str:
        """
        Upload a salon image to Spaces

        Args:
            file: The uploaded file
            salon_id: Salon ID
            image_type: Type of image (cover, gallery)

        Returns:
            Public URL of the uploaded file
        """
        try:
            # Get file extension
            ext = self._get_file_extension(file.filename)

            # Build S3 key
            if image_type == "cover":
                s3_key = f"marketplace/salons/{salon_id}/cover.{ext}"
            else:
                # For gallery images, use timestamp to avoid conflicts
                import time
                timestamp = int(time.time())
                s3_key = f"marketplace/salons/{salon_id}/gallery/{timestamp}.{ext}"

            # Read file content
            file_content = await file.read()
            file_obj = io.BytesIO(file_content)

            # Upload to Spaces
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ACL': 'public-read',
                    'ContentType': self._get_content_type(file.filename),
                    'CacheControl': 'max-age=31536000'
                }
            )

            # Generate public URL
            if self.cdn_endpoint:
                url = f"{self.cdn_endpoint}/{s3_key}"
            else:
                url = f"{settings.do_spaces_endpoint}/{self.bucket_name}/{s3_key}"

            logger.info(f"Salon image uploaded successfully for salon {salon_id}: {url}")
            return url

        except NoCredentialsError:
            logger.error("Credentials not available for Spaces")
            raise HTTPException(status_code=500, detail="Storage credentials not configured")
        except ClientError as e:
            logger.error(f"Error uploading to Spaces: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during upload: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload file")
        finally:
            # Reset file pointer
            await file.seek(0)

    async def delete_salon_image(
        self,
        salon_id: int,
        current_url: Optional[str] = None
    ) -> bool:
        """
        Delete a salon's cover image from Spaces

        Args:
            salon_id: Salon ID
            current_url: Current image URL (for extracting extension)

        Returns:
            True if deleted successfully
        """
        try:
            extensions = ['jpg', 'jpeg', 'png', 'webp', 'gif']

            if current_url:
                ext = current_url.split('.')[-1].split('?')[0].lower()
                if ext in extensions:
                    extensions = [ext]

            deleted = False
            for ext in extensions:
                s3_key = f"marketplace/salons/{salon_id}/cover.{ext}"
                try:
                    self.s3_client.delete_object(
                        Bucket=self.bucket_name,
                        Key=s3_key
                    )
                    logger.info(f"Salon image deleted successfully: {s3_key}")
                    deleted = True
                    break
                except ClientError as e:
                    if e.response['Error']['Code'] != 'NoSuchKey':
                        logger.error(f"Error deleting {s3_key}: {e}")
                    continue

            return deleted

        except Exception as e:
            logger.error(f"Unexpected error during salon image deletion: {e}")
            return False

    def check_bucket_exists(self) -> bool:
        """Check if the configured bucket exists"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError:
            return False


# Singleton instance
storage_service = StorageService()
