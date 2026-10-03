import json
import uuid
import io
import logging
from decimal import Decimal
from django.contrib import admin, messages
from django.urls import path
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied
from django.utils.text import slugify
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile

from .models import BulkStockProduct, BulkStockProductImage, Category, Product, ProductImage
from .image_utils import convert_image_data_to_web_friendly

logger = logging.getLogger(__name__)


def _process_uploaded_file(file, default_name='image.jpg'):
    """Converts uploaded image (HEIC/RAW/large images up to 5MB+) to high-quality web JPEG."""
    if not file:
        return None
    try:
        name = getattr(file, 'name', default_name)
        if hasattr(file, 'seek') and callable(file.seek):
            try:
                file.seek(0)
            except Exception:
                pass
        if hasattr(file, 'temporary_file_path'):
            with open(file.temporary_file_path(), 'rb') as fp:
                content = fp.read()
        else:
            content = file.read()
            if hasattr(file, 'seek') and callable(file.seek):
                try:
                    file.seek(0)
                except Exception:
                    pass
        conv_bytes, new_name, mime = convert_image_data_to_web_friendly(content, name)
        return InMemoryUploadedFile(
            file=io.BytesIO(conv_bytes),
            field_name='image',
            name=new_name,
            content_type=mime,
            size=len(conv_bytes),
            charset=None
        )
    except Exception as err:
        logger.error(f"Error converting image {getattr(file, 'name', 'unknown')}: {err}")
        return file


class BulkStockAdmin(admin.ModelAdmin):
    change_list_template = 'admin/shop/bulk_stock.html'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('save-draft/', self.admin_site.admin_view(self.save_draft_view), name='shop_bulkstock_save_draft'),
            path('publish/', self.admin_site.admin_view(self.publish_view), name='shop_bulkstock_publish'),
            path('delete-rows/', self.admin_site.admin_view(self.delete_rows_view), name='shop_bulkstock_delete_rows'),
            path('clear-all/', self.admin_site.admin_view(self.clear_all_view), name='shop_bulkstock_clear_all'),
            path('upload-image/', self.admin_site.admin_view(self.upload_image_view), name='shop_bulkstock_upload_image'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
            raise PermissionDenied("You do not have permission to access Bulk Stock.")

        extra_context = extra_context or {}

        # 1. Categories
        categories = Category.objects.filter(is_active=True).order_by('name')
        categories_data = [
            {'id': cat.id, 'name': cat.name, 'slug': cat.slug}
            for cat in categories
        ]

        # 2. Existing Bulk Stock Products
        bulk_items = BulkStockProduct.objects.select_related('category').prefetch_related('images').all()
        bulk_data = []
        for item in bulk_items:
            extra_imgs = [img.image.url for img in item.images.all() if img.image]
            bulk_data.append({
                'id': item.id,
                'name': item.name or '',
                'category_id': item.category_id or '',
                'category_name': item.category.name if item.category else '',
                'price': float(item.price) if item.price is not None else '',
                'offer_price': float(item.offer_price) if item.offer_price is not None else '',
                'discount_percentage': item.discount_percentage,
                'sku': item.sku or '',
                'stock': item.stock,
                'image_url': item.image.url if item.image else '',
                'status': item.status,
                'short_description': item.short_description or '',
                'description': item.description or '',
                'fabric': item.fabric or '',
                'color': item.color or '',
                'material': item.material or '',
                'occasion': item.occasion or '',
                'zari_type': item.zari_type or '',
                'saree_length': item.saree_length or '',
                'authenticity': item.authenticity or '',
                'specifications': item.specifications or '',
                'meta_title': item.meta_title or '',
                'meta_description': item.meta_description or '',
                'meta_keywords': item.meta_keywords or '',
                'is_active': item.is_active,
                'is_featured': item.is_featured,
                'is_trending': item.is_trending,
                'is_new_arrival': item.is_new_arrival,
                'is_best_seller': item.is_best_seller,
                'is_today_deal': item.is_today_deal,
                'video_url': item.video_url or '',
                'tags': item.tags or '',
                'extra_images': extra_imgs,
            })

        context = {
            **self.admin_site.each_context(request),
            'opts': self.opts,
            'app_label': self.opts.app_label,
            'module_name': str(self.opts.verbose_name_plural),
            'title': "Bulk Stock",
            'categories': categories,
            'categories_json': json.dumps(categories_data),
            'bulk_products_json': json.dumps(bulk_data),
            'total_bulk_count': bulk_items.count(),
            **(extra_context or {}),
        }

        return render(request, self.change_list_template, context)

    def save_draft_view(self, request):
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)

        try:
            # Handle JSON or FormData payload
            raw_data = request.POST.get('products_data')
            if raw_data:
                products_list = json.loads(raw_data)
            else:
                products_list = json.loads(request.body.decode('utf-8'))

            if isinstance(products_list, dict):
                products_list = products_list.get('products', [])
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Invalid request data: {str(e)}'}, status=400)

        saved_items = []
        try:
            with transaction.atomic():
                for idx, item_data in enumerate(products_list):
                    item_id = item_data.get('id')
                    name = str(item_data.get('name', '')).strip()
                    category_id = item_data.get('category_id')
                    price = item_data.get('price')
                    offer_price = item_data.get('offer_price')
                    sku = str(item_data.get('sku', '')).strip()
                    stock = item_data.get('stock', 1)

                    # Category foreign key
                    cat_obj = None
                    if category_id:
                        try:
                            cat_obj = Category.objects.get(id=int(category_id))
                        except (Category.DoesNotExist, ValueError):
                            pass

                    # Parse numbers safely
                    price_dec = None
                    if price not in (None, '', 'null'):
                        try:
                            price_dec = Decimal(str(price))
                        except Exception:
                            pass

                    offer_dec = None
                    if offer_price not in (None, '', 'null'):
                        try:
                            offer_dec = Decimal(str(offer_price))
                        except Exception:
                            pass

                    try:
                        stock_int = int(stock)
                    except Exception:
                        stock_int = 1

                    if item_id:
                        bulk_obj = BulkStockProduct.objects.filter(id=item_id).first()
                        if not bulk_obj:
                            bulk_obj = BulkStockProduct()
                    else:
                        bulk_obj = BulkStockProduct()

                    bulk_obj.name = name
                    bulk_obj.category = cat_obj
                    bulk_obj.price = price_dec
                    bulk_obj.offer_price = offer_dec
                    bulk_obj.sku = sku
                    bulk_obj.stock = stock_int
                    bulk_obj.status = 'DRAFT'
                    bulk_obj.created_by = request.user

                    # Marketing & Flags
                    if 'is_active' in item_data:
                        bulk_obj.is_active = bool(item_data['is_active'])
                    if 'is_featured' in item_data:
                        bulk_obj.is_featured = bool(item_data['is_featured'])
                    if 'is_trending' in item_data:
                        bulk_obj.is_trending = bool(item_data['is_trending'])
                    if 'is_new_arrival' in item_data:
                        bulk_obj.is_new_arrival = bool(item_data['is_new_arrival'])
                    if 'is_best_seller' in item_data:
                        bulk_obj.is_best_seller = bool(item_data['is_best_seller'])
                    if 'is_today_deal' in item_data:
                        bulk_obj.is_today_deal = bool(item_data['is_today_deal'])

                    # Media & Tags
                    if 'video_url' in item_data:
                        bulk_obj.video_url = item_data['video_url']
                    if 'tags' in item_data:
                        bulk_obj.tags = item_data['tags']

                    # Extra specs if provided
                    if 'short_description' in item_data:
                        bulk_obj.short_description = item_data['short_description']
                    if 'description' in item_data:
                        bulk_obj.description = item_data['description']
                    if 'fabric' in item_data:
                        bulk_obj.fabric = item_data['fabric']
                    if 'color' in item_data:
                        bulk_obj.color = item_data['color']
                    if 'material' in item_data:
                        bulk_obj.material = item_data['material']
                    if 'occasion' in item_data:
                        bulk_obj.occasion = item_data['occasion']
                    if 'zari_type' in item_data:
                        bulk_obj.zari_type = item_data['zari_type']
                    if 'saree_length' in item_data:
                        bulk_obj.saree_length = item_data['saree_length']
                    if 'authenticity' in item_data:
                        bulk_obj.authenticity = item_data['authenticity']
                    if 'specifications' in item_data:
                        bulk_obj.specifications = item_data['specifications']
                    if 'meta_title' in item_data:
                        bulk_obj.meta_title = item_data['meta_title']
                    if 'meta_description' in item_data:
                        bulk_obj.meta_description = item_data['meta_description']
                    if 'meta_keywords' in item_data:
                        bulk_obj.meta_keywords = item_data['meta_keywords']

                    # Check for primary uploaded file (Slot 0 / first image)
                    temp_key = str(item_data.get('temp_id') or '')
                    item_id_key = str(item_id or '')
                    primary_file = (
                        request.FILES.get(f"image_{idx}_0") or 
                        request.FILES.get(f"image_{temp_key}_0") or 
                        request.FILES.get(f"image_{item_id_key}_0") or 
                        request.FILES.get(f"image_{idx}") or 
                        request.FILES.get(f"image_{temp_key}") or 
                        request.FILES.get(f"image_{item_id_key}")
                    )
                    if primary_file:
                        bulk_obj.image = _process_uploaded_file(primary_file, 'saree.jpg')

                    bulk_obj.save()

                    # Check for extra uploaded images (Slot 1, 2, 3... second, third, fourth)
                    for slot in range(1, 20):
                        extra_file = (
                            request.FILES.get(f"image_{idx}_{slot}") or 
                            request.FILES.get(f"image_{temp_key}_{slot}") or 
                            request.FILES.get(f"image_{item_id_key}_{slot}")
                        )
                        if extra_file:
                            BulkStockProductImage.objects.create(
                                bulk_product=bulk_obj,
                                image=_process_uploaded_file(extra_file, f"extra_{slot}.jpg"),
                                display_order=slot
                            )

                    saved_items.append({
                        'id': bulk_obj.id,
                        'name': bulk_obj.name,
                        'category_id': bulk_obj.category_id or '',
                        'category_name': bulk_obj.category.name if bulk_obj.category else '',
                        'price': float(bulk_obj.price) if bulk_obj.price else '',
                        'offer_price': float(bulk_obj.offer_price) if bulk_obj.offer_price else '',
                        'sku': bulk_obj.sku,
                        'stock': bulk_obj.stock,
                        'image_url': bulk_obj.image.url if bulk_obj.image else '',
                        'extra_images': [img.image.url for img in bulk_obj.images.all() if img.image],
                        'status': bulk_obj.status,
                        'temp_id': item_data.get('temp_id'),
                        'is_active': bulk_obj.is_active,
                        'is_featured': bulk_obj.is_featured,
                        'is_trending': bulk_obj.is_trending,
                        'is_new_arrival': bulk_obj.is_new_arrival,
                        'is_best_seller': bulk_obj.is_best_seller,
                        'is_today_deal': bulk_obj.is_today_deal,
                        'video_url': bulk_obj.video_url or '',
                        'tags': bulk_obj.tags or '',
                        'short_description': bulk_obj.short_description or '',
                        'description': bulk_obj.description or '',
                        'fabric': bulk_obj.fabric or '',
                        'color': bulk_obj.color or '',
                        'material': bulk_obj.material or '',
                        'occasion': bulk_obj.occasion or '',
                        'zari_type': bulk_obj.zari_type or '',
                        'saree_length': bulk_obj.saree_length or '',
                        'authenticity': bulk_obj.authenticity or '',
                        'specifications': bulk_obj.specifications or '',
                        'meta_title': bulk_obj.meta_title or '',
                        'meta_description': bulk_obj.meta_description or '',
                        'meta_keywords': bulk_obj.meta_keywords or '',
                    })

            return JsonResponse({
                'success': True,
                'message': f"{len(saved_items)} product(s) saved to Bulk Stock draft.",
                'saved_items': saved_items,
                'saved_count': len(saved_items),
                'total_count': BulkStockProduct.objects.count()
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': f"Failed to save draft: {str(e)}"}, status=500)

    def publish_view(self, request):
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)

        try:
            data = json.loads(request.body.decode('utf-8'))
            product_ids = data.get('product_ids') or data.get('selected_ids') or []
            publish_all = data.get('publish_all', False)
        except Exception:
            product_ids = request.POST.getlist('product_ids') or request.POST.getlist('selected_ids')
            publish_all = request.POST.get('publish_all') == 'true'

        if publish_all:
            queryset = BulkStockProduct.objects.all()
        else:
            queryset = BulkStockProduct.objects.filter(id__in=product_ids)

        if not queryset.exists():
            return JsonResponse({'success': False, 'error': 'No products selected for publishing.'}, status=400)

        published_ids = []
        errors = []

        # Process each product in a savepoint so that valid products succeed even if one fails
        for item in queryset:
            sp = transaction.savepoint()
            try:
                # 1. Validation
                if not item.name or not item.name.strip():
                    raise ValueError(f"Product #{item.id} has no name.")

                if not item.price or item.price <= 0:
                    raise ValueError(f"Product '{item.name}' requires a valid price greater than 0.")

                if not item.category:
                    raise ValueError(f"Product '{item.name}' requires a category.")

                # Generate or validate SKU
                sku = (item.sku or '').strip()
                if not sku:
                    sku = f"RS-{uuid.uuid4().hex[:8].upper()}"
                elif Product.objects.filter(sku=sku).exists():
                    raise ValueError(f"SKU '{sku}' already exists on a live product.")

                # Generate unique slug
                base_slug = slugify(item.name)
                unique_slug = base_slug
                counter = 1
                while Product.objects.filter(slug=unique_slug).exists():
                    unique_slug = f"{base_slug}-{counter}"
                    counter += 1

                # 2. Create Live Product
                live_p = Product.objects.create(
                    name=item.name.strip(),
                    slug=unique_slug,
                    sku=sku,
                    price=item.price,
                    offer_price=item.offer_price,
                    discount_percentage=item.discount_percentage,
                    stock=max(0, item.stock),
                    short_description=item.short_description or '',
                    description=item.description or item.name.strip(),
                    fabric=item.fabric or '',
                    color=item.color or '',
                    material=item.material or '',
                    occasion=item.occasion or '',
                    zari_type=item.zari_type or '',
                    saree_length=item.saree_length or '',
                    authenticity=item.authenticity or '',
                    specifications=item.specifications or '',
                    meta_title=item.meta_title or '',
                    meta_description=item.meta_description or '',
                    meta_keywords=item.meta_keywords or '',
                    is_active=item.is_active,
                    is_featured=item.is_featured,
                    is_trending=item.is_trending,
                    is_new_arrival=item.is_new_arrival,
                    is_best_seller=item.is_best_seller,
                    is_today_deal=item.is_today_deal,
                    video_url=item.video_url,
                    tags=item.tags or '',
                )

                # Add Category
                live_p.categories.add(item.category)

                # Attach Primary Image
                if item.image:
                    ProductImage.objects.create(product=live_p, image=item.image, display_order=0)

                # Attach Extra Images
                for idx, extra_img in enumerate(item.images.all(), start=1):
                    if extra_img.image:
                        ProductImage.objects.create(product=live_p, image=extra_img.image, display_order=idx)

                # 3. Clean up from Bulk Stock
                item_id = item.id
                item.delete()
                published_ids.append(item_id)
                transaction.savepoint_commit(sp)

            except Exception as e:
                transaction.savepoint_rollback(sp)
                errors.append(str(e))

        remaining_count = BulkStockProduct.objects.count()

        if not published_ids and errors:
            return JsonResponse({
                'success': False,
                'published_count': 0,
                'published_ids': [],
                'error': '; '.join(errors),
                'errors': errors,
                'remaining_count': remaining_count,
            }, status=400)

        return JsonResponse({
            'success': len(published_ids) > 0,
            'published_count': len(published_ids),
            'published_ids': published_ids,
            'errors': errors,
            'remaining_count': remaining_count,
            'message': f"Successfully published {len(published_ids)} product(s) to live products." if published_ids else "Failed to publish products."
        })

    def delete_rows_view(self, request):
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)

        try:
            data = json.loads(request.body.decode('utf-8'))
            product_ids = data.get('product_ids') or data.get('ids') or []
        except Exception:
            product_ids = request.POST.getlist('product_ids') or request.POST.getlist('ids')

        deleted_count, _ = BulkStockProduct.objects.filter(id__in=product_ids).delete()
        return JsonResponse({
            'success': True,
            'deleted_count': deleted_count,
            'remaining_count': BulkStockProduct.objects.count(),
            'message': f"{deleted_count} product(s) removed from Bulk Stock."
        })

    def clear_all_view(self, request):
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)

        count, _ = BulkStockProduct.objects.all().delete()
        return JsonResponse({
            'success': True,
            'message': f"All {count} product(s) cleared from Bulk Stock.",
            'remaining_count': 0
        })

    def upload_image_view(self, request):
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)

        file = request.FILES.get('image')
        if not file:
            return JsonResponse({'success': False, 'error': 'No file uploaded'}, status=400)

        processed = _process_uploaded_file(file, 'image.jpg')
        file_name = getattr(processed, 'name', 'image.jpg')
        if hasattr(processed, 'seek') and callable(processed.seek):
            try:
                processed.seek(0)
            except Exception:
                pass
        if hasattr(processed, 'read'):
            file_bytes = processed.read()
        else:
            file_bytes = file.read()

        # Save to bulk_stock directory
        file_path = default_storage.save(f"bulk_stock/{uuid.uuid4().hex}_{file_name}", ContentFile(file_bytes))
        file_url = default_storage.url(file_path)

        # If existing product ID provided, attach it
        product_id = request.POST.get('product_id') or request.POST.get('row_id')
        if product_id:
            bulk_p = BulkStockProduct.objects.filter(id=product_id).first()
            if bulk_p:
                bulk_p.image = file_path
                bulk_p.save()

        return JsonResponse({
            'success': True,
            'image_url': file_url,
            'image_path': file_path,
        })
