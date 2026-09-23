import io
from django.test import TestCase
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import validate_image_file_extension, get_available_image_extensions
from django.core.exceptions import ValidationError
from PIL import Image
from shop.models import Product, ProductImage, Category
from shop.image_utils import ALL_ALLOWED_IMAGE_EXTENSIONS, convert_image_data_to_web_friendly


class UniversalImageHandlingTests(TestCase):
    def test_all_image_extensions_in_available_extensions(self):
        """Verify that get_available_image_extensions and validator support all requested image types."""
        available = get_available_image_extensions()
        for ext in ['dng', 'heic', 'heif', 'raw', 'cr2', 'cr3', 'nef', 'arw', 'svg', 'avif', 'webp', 'jpg', 'png']:
            self.assertIn(ext, available, f"Extension {ext} should be in available image extensions")

    def test_validator_accepts_dng_and_raw_extensions(self):
        """Test validate_image_file_extension accepts dng, raw, heic, and uppercase variations."""
        for filename in ['saree_front.dng', 'SAREE_BACK.DNG', 'photo.heic', 'photo.raw', 'photo.cr2', 'photo.svg']:
            dummy_file = SimpleUploadedFile(filename, b'dummy content', content_type='application/octet-stream')
            try:
                validate_image_file_extension(dummy_file)
            except ValidationError as e:
                self.fail(f"Validation unexpectedly failed for {filename}: {e}")

    def test_dng_upload_conversion_to_jpeg(self):
        """Test that a DNG image uploaded through ImageField is automatically converted to JPEG."""
        # Create a valid image encoded as TIFF (DNG specification basis)
        buf = io.BytesIO()
        Image.new('RGB', (120, 120), color=(175, 4, 70)).save(buf, format='TIFF')
        dng_file = SimpleUploadedFile('kanchipuram_red.dng', buf.getvalue(), content_type='image/x-adobe-dng')

        field = forms.ImageField()
        cleaned_file = field.clean(dng_file)

        self.assertTrue(cleaned_file.name.endswith('.jpg'), f"Expected .jpg extension but got {cleaned_file.name}")
        self.assertEqual(cleaned_file.content_type, 'image/jpeg')

        # Verify Pillow can open the cleaned result as JPEG
        cleaned_file.seek(0)
        img = Image.open(cleaned_file)
        self.assertEqual(img.format, 'JPEG')
        self.assertEqual(img.size, (120, 120))

    def test_tiff_upload_conversion_to_jpeg(self):
        """Test that TIFF images are converted to JPEG."""
        buf = io.BytesIO()
        Image.new('RGB', (50, 50), color='green').save(buf, format='TIFF')
        tiff_file = SimpleUploadedFile('fabric.tiff', buf.getvalue(), content_type='image/tiff')

        field = forms.ImageField()
        cleaned = field.clean(tiff_file)
        self.assertTrue(cleaned.name.endswith('.jpg'))
        self.assertEqual(cleaned.content_type, 'image/jpeg')

    def test_svg_upload_preservation(self):
        """Test that SVG vector images are validated and preserved."""
        svg_bytes = b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><circle cx="50" cy="50" r="40" fill="gold" /></svg>'
        svg_file = SimpleUploadedFile('logo.svg', svg_bytes, content_type='image/svg+xml')

        field = forms.ImageField()
        cleaned = field.clean(svg_file)
        self.assertEqual(cleaned.name, 'logo.svg')
        self.assertEqual(cleaned.content_type, 'image/svg+xml')

    def test_standard_jpeg_png_preserved(self):
        """Test that standard JPEG and PNG files are accepted and preserved."""
        # JPEG
        buf = io.BytesIO()
        Image.new('RGB', (60, 60), color='blue').save(buf, format='JPEG')
        jpg_file = SimpleUploadedFile('normal.jpg', buf.getvalue(), content_type='image/jpeg')
        cleaned_jpg = forms.ImageField().clean(jpg_file)
        self.assertEqual(cleaned_jpg.name, 'normal.jpg')

        # PNG
        buf_png = io.BytesIO()
        Image.new('RGBA', (60, 60), color=(0, 255, 0, 128)).save(buf_png, format='PNG')
        png_file = SimpleUploadedFile('badge.png', buf_png.getvalue(), content_type='image/png')
        cleaned_png = forms.ImageField().clean(png_file)
        self.assertEqual(cleaned_png.name, 'badge.png')

    def test_corrupt_file_raises_validation_error(self):
        """Test that corrupted non-image files are properly rejected."""
        bad_file = SimpleUploadedFile('fake.jpg', b'NOT AN IMAGE CONTENT AT ALL', content_type='image/jpeg')
        with self.assertRaises(ValidationError):
            forms.ImageField().clean(bad_file)

    def test_product_image_model_form_accepts_dng(self):
        """Test that ProductImage ModelForm accepts DNG upload and saves cleanly."""
        class ProductImageForm(forms.ModelForm):
            class Meta:
                model = ProductImage
                fields = ['image', 'display_order']

        category = Category.objects.create(name="Test Silk", slug="test-silk")
        product = Product.objects.create(
            name="Test Royal Saree",
            sku="RSS-TEST-DNG",
            price=5000,
            stock=5
        )

        buf = io.BytesIO()
        Image.new('RGB', (100, 100), color=(200, 100, 50)).save(buf, format='TIFF')
        dng_file = SimpleUploadedFile('traditional_saree.dng', buf.getvalue(), content_type='image/x-adobe-dng')

        form = ProductImageForm(
            data={'display_order': 1},
            files={'image': dng_file}
        )
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        instance = form.save(commit=False)
        instance.product = product
        self.assertTrue(instance.image.name.endswith('.jpg'), f"Image name should end with .jpg, got {instance.image.name}")

    def test_large_image_over_10mb_automatically_compressed_below_limit(self):
        """Test that an image > 10MB (like the 11,127,485 byte error in Cloudinary) is auto-compressed below 5MB."""
        import numpy as np
        # Create a large high-resolution image (3500x3500) that produces a >11MB JPEG
        arr = np.random.randint(40, 220, (3500, 3500, 3), dtype=np.uint8)
        img = Image.fromarray(arr)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        raw_bytes = buf.getvalue()
        self.assertGreater(len(raw_bytes), 10 * 1024 * 1024, "Test requires raw image > 10MB")

        field = forms.ImageField()
        large_file = SimpleUploadedFile('giant_saree_photo.jpg', raw_bytes, content_type='image/jpeg')
        cleaned = field.clean(large_file)

        # Must be strictly under Cloudinary's 10,485,760 byte limit
        self.assertLess(cleaned.size, 10485760, f"Cleaned image size {cleaned.size} must be under Cloudinary 10MB limit")
        self.assertLessEqual(cleaned.size, 5 * 1024 * 1024, f"Cleaned image size {cleaned.size} must be under 5MB target")

    def test_upload_more_than_5_images_for_one_product(self):
        """Test that more than 5 images (e.g. 8 images) can be added to a single product without issue."""
        category = Category.objects.create(name="Multi Test Silk", slug="multi-test-silk")
        product = Product.objects.create(
            name="Grand Kanchipuram Bridal Saree",
            sku="RSS-MULTI-IMG-TEST",
            price=12000,
            stock=10
        )

        # Upload 8 images for this one product
        for i in range(1, 9):
            buf = io.BytesIO()
            Image.new('RGB', (100, 100), color=(i * 20, 50, 100)).save(buf, format='JPEG')
            file_upload = SimpleUploadedFile(f'saree_angle_{i}.jpg', buf.getvalue(), content_type='image/jpeg')
            ProductImage.objects.create(
                product=product,
                image=file_upload,
                display_order=i
            )

        self.assertEqual(product.images.count(), 8)
        images = list(product.images.all())
        self.assertEqual(len(images), 8)
        self.assertEqual([img.display_order for img in images], [1, 2, 3, 4, 5, 6, 7, 8])
