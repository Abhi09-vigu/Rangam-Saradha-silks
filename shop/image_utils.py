"""
Universal Image Handling & Conversion Utility for Rangam Saradha Silks.
Supports all image formats including RAW (DNG, CR2, NEF, ARW, etc.),
HEIC/HEIF (iPhone/modern phones), SVG, WebP, AVIF, TIFF, and standard web images.

Automatically converts camera RAW, DNG, HEIC, and TIFF files to high-quality,
web-optimized JPEGs upon upload so that:
1. File upload validation in Django Admin and frontend never fails on valid image types.
2. Images render natively and smoothly across all web browsers and mobile devices.
3. Loading speed is optimized (converting 40MB raw files to ~1MB high-res JPEGs).
"""

import os
import io
from PIL import Image, ImageOps

# Register HEIC opener if available
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

# Comprehensive list of allowed image extensions (lowercase without dot)
ALL_ALLOWED_IMAGE_EXTENSIONS = [
    # Standard web formats
    'jpg', 'jpeg', 'jpe', 'jif', 'jfif', 'jfi',
    'png', 'webp', 'gif', 'bmp', 'dib', 'ico',
    'svg', 'svgz', 'avif', 'apng',
    # Camera RAW formats (including mobile raw formats like Apple ProRAW & Samsung Expert RAW)
    'dng', 'raw', 'cr2', 'cr3', 'nef', 'nrw', 'arw', 'srf', 'sr2',
    'orf', 'rw2', 'pef', 'ptx', 'raf', 'erf', 'kdc', 'k25', 'dcr',
    'mos', 'mef', 'crw', 'rwl', 'srw', '3fr', 'fff',
    # High Efficiency formats
    'heic', 'heif', 'hif',
    # Professional / Print formats
    'tif', 'tiff', 'psd', 'psb', 'eps', 'ai', 'pdf',
    # Pillow formats
    'blp', 'bufr', 'cur', 'pcx', 'dcx', 'dds', 'fit', 'fits',
    'fli', 'flc', 'ftc', 'ftu', 'gbr', 'grib', 'h5', 'hdf',
    'jp2', 'j2k', 'jpc', 'jpf', 'jpx', 'j2c', 'icns', 'im', 'iim',
    'mpg', 'mpeg', 'mpo', 'msp', 'palm', 'pcd', 'pxr', 'pbm',
    'pgm', 'ppm', 'pnm', 'pfm', 'qoi', 'bw', 'rgb', 'rgba',
    'sgi', 'ras', 'tga', 'icb', 'vda', 'vst', 'wmf', 'emf', 'xbm', 'xpm'
]

RAW_EXTENSIONS = {
    'dng', 'raw', 'cr2', 'cr3', 'nef', 'nrw', 'arw', 'srf', 'sr2',
    'orf', 'rw2', 'pef', 'ptx', 'raf', 'erf', 'kdc', 'k25', 'dcr',
    'mos', 'mef', 'crw', 'rwl', 'srw', '3fr', 'fff'
}

CONVERT_TO_JPEG_EXTENSIONS = RAW_EXTENSIONS | {
    'heic', 'heif', 'hif', 'tif', 'tiff', 'bmp', 'dib', 'psd', 'psb'
}


MAX_IMAGE_DIMENSION = 2560  # Ultra-crisp for 4K and saree zoom
MAX_ALLOWED_FILE_BYTES = 5 * 1024 * 1024  # 5 MB target ceiling (Cloudinary limit is 10,485,760 bytes = 10 MB)
AUTO_RESIZE_BYTES_THRESHOLD = 2 * 1024 * 1024  # 2 MB - files larger than this get compressed


def convert_image_data_to_web_friendly(content_bytes, original_name):
    """
    Takes raw bytes and filename of an uploaded image.
    - If it's SVG: validates and returns (content_bytes, original_name, 'image/svg+xml').
    - If it's RAW/DNG/HEIC/TIFF/BMP: develops/converts to high-quality JPEG.
    - If it's standard web format (JPG, PNG, WebP, GIF):
      * If small (<= 2MB) and within 2560px dimensions, preserves original.
      * If large (> 2MB) or huge dimensions (> 2560px), auto-resizes and optimizes to JPEG
        so that file size is ~400KB-1.5MB and strictly stays below Cloudinary's 10MB limit.
    - Auto-rotates EXIF orientation to ensure smartphone photos always stand upright.
    """
    ext = os.path.splitext(original_name)[1].lower().lstrip('.')
    base_name = os.path.splitext(original_name)[0]

    # Handle SVG
    if ext in ('svg', 'svgz'):
        text = content_bytes.decode('utf-8', errors='ignore')
        if '<svg' in text.lower():
            return content_bytes, original_name, 'image/svg+xml'
        raise ValueError("Invalid SVG image file.")

    img = None

    # For RAW and DNG files, try rawpy first
    if ext in RAW_EXTENSIONS:
        try:
            import rawpy
            with rawpy.imread(io.BytesIO(content_bytes)) as raw:
                rgb = raw.postprocess(use_camera_wb=True, half_size=False)
                img = Image.fromarray(rgb)
        except Exception:
            # Fall back to Pillow (e.g. for Linear DNG / TIFF-based DNG)
            pass

    # If not loaded yet, try Pillow (which handles HEIC via pillow_heif, AVIF, TIFF, WebP, PNG, JPG, etc.)
    if img is None:
        try:
            img = Image.open(io.BytesIO(content_bytes))
            img.load()
        except Exception as exc:
            raise ValueError(f"Unable to decode image: {exc}") from exc

    # Auto-orient EXIF orientation (fixes portrait mobile photos showing sideways)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Check if this image already qualifies as a small, web-ready asset
    is_standard_web = ext in ('jpg', 'jpeg', 'png', 'webp', 'gif')
    is_small_size = len(content_bytes) <= AUTO_RESIZE_BYTES_THRESHOLD
    is_within_dimensions = max(img.size) <= MAX_IMAGE_DIMENSION

    # Special handling for animated GIF under 8MB
    if ext == 'gif' and len(content_bytes) < 8 * 1024 * 1024:
        return content_bytes, original_name, 'image/gif'

    # If it is already small, within safe dimensions, and not a format needing conversion
    if is_standard_web and is_small_size and is_within_dimensions and ext not in CONVERT_TO_JPEG_EXTENSIONS:
        mime = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
        return content_bytes, original_name, mime

    # 1. Resize if image dimensions exceed MAX_IMAGE_DIMENSION (2560px)
    if max(img.size) > MAX_IMAGE_DIMENSION:
        img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)

    # 2. Preserve PNG transparency if it is relatively small
    if ext == 'png' and (img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info)):
        if len(content_bytes) <= 3 * 1024 * 1024 and max(img.size) <= MAX_IMAGE_DIMENSION:
            out_buf = io.BytesIO()
            img.save(out_buf, format='PNG', optimize=True)
            png_bytes = out_buf.getvalue()
            if len(png_bytes) < MAX_ALLOWED_FILE_BYTES:
                return png_bytes, original_name, 'image/png'

    # Convert to RGB mode (blending transparent layers onto white background)
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # 3. Save as high-quality web-optimized JPEG
    quality = 88
    out_buf = io.BytesIO()
    img.save(out_buf, format='JPEG', quality=quality, optimize=True)
    out_bytes = out_buf.getvalue()

    # Progressive step-down if output exceeds 5 MB (Cloudinary limit is 10,485,760 bytes = 10 MB)
    while len(out_bytes) > MAX_ALLOWED_FILE_BYTES and quality > 60:
        quality -= 8
        out_buf = io.BytesIO()
        img.save(out_buf, format='JPEG', quality=quality, optimize=True)
        out_bytes = out_buf.getvalue()

    # Extreme safety fallback for ultra-dense patterns
    if len(out_bytes) > 8 * 1024 * 1024:
        img.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
        out_buf = io.BytesIO()
        img.save(out_buf, format='JPEG', quality=75, optimize=True)
        out_bytes = out_buf.getvalue()

    new_name = f"{base_name}.jpg"
    return out_bytes, new_name, 'image/jpeg'


_initialized = False

def setup_universal_image_handling():
    """
    Globally registers all image formats and hooks into Django's
    validators and forms.ImageField to allow all image formats seamlessly.
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    # 1. Register HEIC in Pillow
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        pass

    # 2. Register RAW extensions with Pillow TIFF plugin
    from PIL import Image, TiffImagePlugin
    for raw_ext in ('.dng', '.DNG', '.raw', '.RAW', '.cr2', '.CR2', '.nef', '.NEF', '.arw', '.ARW'):
        try:
            Image.register_extension(TiffImagePlugin.TiffImageFile.format, raw_ext)
        except Exception:
            pass

    # 3. Enhance Django core validators
    import django.core.validators as django_validators
    orig_get_available = django_validators.get_available_image_extensions

    def universal_get_available_image_extensions():
        try:
            base_list = orig_get_available()
        except Exception:
            base_list = []
        combined = set(base_list) | set(ALL_ALLOWED_IMAGE_EXTENSIONS)
        return list(combined)

    django_validators.get_available_image_extensions = universal_get_available_image_extensions

    # Also update validate_image_file_extension to accept all allowed image extensions
    def universal_validate_image_file_extension(value):
        ext = os.path.splitext(getattr(value, 'name', ''))[1][1:].lower()
        if ext in ALL_ALLOWED_IMAGE_EXTENSIONS:
            return
        # If not explicitly listed, fall back to default validator
        return django_validators.FileExtensionValidator(
            allowed_extensions=universal_get_available_image_extensions()
        )(value)

    django_validators.validate_image_file_extension = universal_validate_image_file_extension

    # 4. Enhance django.forms.fields.ImageField
    from django import forms
    from django.core.files.uploadedfile import InMemoryUploadedFile, SimpleUploadedFile
    from django.core.exceptions import ValidationError

    orig_image_field_to_python = forms.ImageField.to_python

    def universal_image_field_to_python(self, data):
        if data is None:
            return None

        # If data has a filename
        name = getattr(data, 'name', '')
        ext = os.path.splitext(name)[1].lower().lstrip('.')

        # Read content bytes
        if hasattr(data, 'temporary_file_path'):
            with open(data.temporary_file_path(), 'rb') as fp:
                content_bytes = fp.read()
        elif hasattr(data, 'read'):
            content_bytes = data.read()
            if hasattr(data, 'seek') and callable(data.seek):
                data.seek(0)
        else:
            content_bytes = data.get('content', b'')

        if not content_bytes:
            return orig_image_field_to_python(self, data)

        # Process / convert to web friendly if needed
        try:
            converted_bytes, new_name, mime = convert_image_data_to_web_friendly(content_bytes, name)
        except Exception as err:
            raise ValidationError(
                self.error_messages["invalid_image"],
                code="invalid_image",
            ) from err

        # Handle SVG specially (Pillow cannot verify SVG XML)
        if ext in ('svg', 'svgz'):
            f = SimpleUploadedFile(
                name=new_name,
                content=converted_bytes,
                content_type='image/svg+xml'
            )
            f.image = None
            f.content_type = 'image/svg+xml'
            return f

        # For raster images (converted or original)
        buf = io.BytesIO(converted_bytes)
        new_uploaded_file = InMemoryUploadedFile(
            file=buf,
            field_name=getattr(data, 'field_name', None),
            name=new_name,
            content_type=mime,
            size=len(converted_bytes),
            charset=None
        )

        return orig_image_field_to_python(self, new_uploaded_file)

    forms.ImageField.to_python = universal_image_field_to_python

    # 5. Make sure file inputs accept all types
    orig_widget_attrs = forms.ImageField.widget_attrs

    def universal_widget_attrs(self, widget):
        attrs = orig_widget_attrs(self, widget)
        if isinstance(widget, forms.FileInput):
            # Accept all images + raw extensions
            attrs['accept'] = "image/*,.dng,.raw,.cr2,.cr3,.nef,.arw,.heic,.heif,.svg"
        return attrs

    forms.ImageField.widget_attrs = universal_widget_attrs
