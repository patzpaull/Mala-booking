# app/utils/image_processor.py

from PIL import Image
import io
import logging
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Utility class for image validation, optimization, and processing
    """

    # Allowed MIME types
    ALLOWED_MIME_TYPES = {
        'image/jpeg',
        'image/jpg',
        'image/png',
        'image/webp',
        'image/gif'
    }

    # Allowed file extensions
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}

    # Size limits (in bytes)
    MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5MB
    MAX_SALON_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

    # Image dimension limits
    AVATAR_SIZE = (512, 512)  # Avatar dimensions
    SALON_COVER_SIZE = (1920, 1080)  # Salon cover dimensions
    MAX_DIMENSION = 4096  # Maximum width or height

    @staticmethod
    def validate_file_type(file: UploadFile) -> bool:
        """
        Validate file type based on MIME type and extension

        Args:
            file: Uploaded file

        Returns:
            True if valid

        Raises:
            HTTPException: If file type is invalid
        """
        # Check MIME type
        if file.content_type not in ImageProcessor.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(ImageProcessor.ALLOWED_MIME_TYPES)}"
            )

        # Check extension
        if '.' not in file.filename:
            raise HTTPException(
                status_code=400,
                detail="File must have an extension"
            )

        ext = file.filename.lower().split('.')[-1]
        if ext not in ImageProcessor.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file extension. Allowed: {', '.join(ImageProcessor.ALLOWED_EXTENSIONS)}"
            )

        return True

    @staticmethod
    async def validate_file_size(file: UploadFile, max_size: int) -> bool:
        """
        Validate file size

        Args:
            file: Uploaded file
            max_size: Maximum allowed size in bytes

        Returns:
            True if valid

        Raises:
            HTTPException: If file size exceeds limit
        """
        # Read file to check size
        content = await file.read()
        file_size = len(content)

        # Reset file pointer
        await file.seek(0)

        if file_size > max_size:
            max_mb = max_size / (1024 * 1024)
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {max_mb:.1f}MB"
            )

        return True

    @staticmethod
    async def validate_avatar(file: UploadFile) -> bool:
        """
        Validate avatar file (type and size)

        Args:
            file: Uploaded file

        Returns:
            True if valid
        """
        ImageProcessor.validate_file_type(file)
        await ImageProcessor.validate_file_size(file, ImageProcessor.MAX_AVATAR_SIZE)
        return True

    @staticmethod
    async def validate_salon_image(file: UploadFile) -> bool:
        """
        Validate salon image file (type and size)

        Args:
            file: Uploaded file

        Returns:
            True if valid
        """
        ImageProcessor.validate_file_type(file)
        await ImageProcessor.validate_file_size(file, ImageProcessor.MAX_SALON_IMAGE_SIZE)
        return True

    @staticmethod
    async def process_avatar(file: UploadFile) -> Tuple[io.BytesIO, str]:
        """
        Process and optimize avatar image

        Args:
            file: Uploaded file

        Returns:
            Tuple of (processed image BytesIO, format)
        """
        try:
            # Read file content
            content = await file.read()
            await file.seek(0)

            # Open image
            img = Image.open(io.BytesIO(content))

            # Convert to RGB if necessary (for JPEG)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background

            # Resize to avatar dimensions (maintain aspect ratio)
            img.thumbnail(ImageProcessor.AVATAR_SIZE, Image.Resampling.LANCZOS)

            # Create square canvas (center the image)
            square_img = Image.new('RGB', ImageProcessor.AVATAR_SIZE, (255, 255, 255))
            offset = ((ImageProcessor.AVATAR_SIZE[0] - img.size[0]) // 2,
                      (ImageProcessor.AVATAR_SIZE[1] - img.size[1]) // 2)
            square_img.paste(img, offset)

            # Save to BytesIO
            output = io.BytesIO()
            square_img.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)

            logger.info(f"Avatar processed successfully: {file.filename}")
            return output, 'jpg'

        except Exception as e:
            logger.error(f"Error processing avatar: {e}")
            raise HTTPException(
                status_code=400,
                detail="Failed to process image. Please ensure it's a valid image file."
            )

    @staticmethod
    async def process_salon_image(file: UploadFile) -> Tuple[io.BytesIO, str]:
        """
        Process and optimize salon cover image

        Args:
            file: Uploaded file

        Returns:
            Tuple of (processed image BytesIO, format)
        """
        try:
            # Read file content
            content = await file.read()
            await file.seek(0)

            # Open image
            img = Image.open(io.BytesIO(content))

            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background

            # Resize to cover dimensions (maintain aspect ratio)
            img.thumbnail(ImageProcessor.SALON_COVER_SIZE, Image.Resampling.LANCZOS)

            # Save to BytesIO
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=90, optimize=True)
            output.seek(0)

            logger.info(f"Salon image processed successfully: {file.filename}")
            return output, 'jpg'

        except Exception as e:
            logger.error(f"Error processing salon image: {e}")
            raise HTTPException(
                status_code=400,
                detail="Failed to process image. Please ensure it's a valid image file."
            )

    @staticmethod
    async def get_image_dimensions(file: UploadFile) -> Tuple[int, int]:
        """
        Get image dimensions

        Args:
            file: Uploaded file

        Returns:
            Tuple of (width, height)
        """
        try:
            content = await file.read()
            await file.seek(0)

            img = Image.open(io.BytesIO(content))
            return img.size

        except Exception as e:
            logger.error(f"Error getting image dimensions: {e}")
            raise HTTPException(
                status_code=400,
                detail="Failed to read image dimensions"
            )


# Singleton instance
image_processor = ImageProcessor()
