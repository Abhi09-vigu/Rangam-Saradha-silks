import json
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.contrib import admin, messages
from django.urls import path, reverse
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, Min, Max, Avg, Count

from .models import Product, Category, ProductPriceChange

logger = logging.getLogger(__name__)


class ProductPriceChangeAdmin(admin.ModelAdmin):
    change_list_template = 'admin/shop/product_price_change.html'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('update-batch/', self.admin_site.admin_view(self.update_batch_view), name='shop_productpricechange_update_batch'),
            path('quick-update-single/', self.admin_site.admin_view(self.quick_update_single_view), name='shop_productpricechange_quick_update'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
            raise PermissionDenied('You do not have permission to access Product Price Change.')

        extra_context = extra_context or {}

        sku_query = request.GET.get('sku', '').strip()
        general_q = request.GET.get('q', '').strip()
        search_term = sku_query if sku_query else general_q
        match_type = request.GET.get('match_type', 'contains').strip()
        category_id = request.GET.get('category', '').strip()
        stock_filter = request.GET.get('stock_status', '').strip()

        # Build query
        filter_query = Q()

        if search_term:
            if match_type == 'exact':
                filter_query &= Q(sku__iexact=search_term)
            elif match_type == 'startswith':
                filter_query &= Q(sku__istartswith=search_term)
            else:  # contains
                filter_query &= (Q(sku__icontains=search_term) | Q(name__icontains=search_term))

        if category_id:
            try:
                filter_query &= Q(categories__id=int(category_id))
            except ValueError:
                pass

        if stock_filter == 'in_stock':
            filter_query &= Q(stock__gt=0)
        elif stock_filter == 'out_of_stock':
            filter_query &= Q(stock__lte=0)

        # Query products
        products_qs = Product.objects.filter(filter_query).distinct().prefetch_related('categories', 'images').order_by('-created_at')

        # Limit to 100 products per page if no search to avoid huge payloads
        total_matching_count = products_qs.count()
        displayed_products = products_qs[:100]

        products_data = []
        for p in displayed_products:
            first_image = p.images.first()
            img_url = first_image.image.url if (first_image and first_image.image) else ''
            categories_str = ', '.join([c.name for c in p.categories.all()[:2]])
            admin_change_url = reverse('custom_admin:shop_product_change', args=[p.id]) if hasattr(self.admin_site, 'name') else f'/admin/shop/product/{p.id}/change/'

            products_data.append({
                'id': p.id,
                'name': p.name,
                'sku': p.sku or '',
                'categories_str': categories_str,
                'price': float(p.price) if p.price is not None else 0.0,
                'offer_price': float(p.offer_price) if p.offer_price is not None else float(p.price or 0.0),
                'discount_percentage': p.discount_percentage,
                'stock': p.stock,
                'is_active': p.is_active,
                'image_url': img_url,
                'admin_change_url': admin_change_url,
            })

        categories = Category.objects.filter(is_active=True).order_by('name')

        context = {
            **self.admin_site.each_context(request),
            'opts': self.opts,
            'app_label': self.opts.app_label,
            'module_name': str(self.opts.verbose_name_plural),
            'title': 'Product Price Change',
            'search_term': search_term,
            'match_type': match_type,
            'selected_category': category_id,
            'selected_stock': stock_filter,
            'categories': categories,
            'products': products_data,
            'total_count': total_matching_count,
            'is_filtered': bool(search_term or category_id or stock_filter),
            **(extra_context or {}),
        }

        return render(request, self.change_list_template, context)

    def update_batch_view(self, request):
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)

        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST

            product_ids = data.get('product_ids', [])
            search_term = data.get('search_term', '').strip()
            match_type = data.get('match_type', 'contains').strip()
            category_id = data.get('category', '').strip()
            update_all_matching = data.get('update_all_matching', False)

            # Price parsing
            raw_price = data.get('price')
            if raw_price is None or str(raw_price).strip() == '':
                return JsonResponse({'success': False, 'error': 'Regular Price (MRP) is required.'}, status=400)

            try:
                new_price = Decimal(str(raw_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if new_price <= Decimal('0'):
                    return JsonResponse({'success': False, 'error': 'Price must be greater than zero.'}, status=400)
            except InvalidOperation:
                return JsonResponse({'success': False, 'error': 'Invalid price value.'}, status=400)

            raw_offer = data.get('offer_price')
            raw_discount = data.get('discount_percentage')

            new_offer_price = None
            if raw_offer is not None and str(raw_offer).strip() != '':
                try:
                    new_offer_price = Decimal(str(raw_offer)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    if new_offer_price > new_price:
                        return JsonResponse({'success': False, 'error': 'Offer price cannot be greater than regular price.'}, status=400)
                    if new_offer_price < Decimal('0'):
                        return JsonResponse({'success': False, 'error': 'Offer price cannot be negative.'}, status=400)
                except InvalidOperation:
                    return JsonResponse({'success': False, 'error': 'Invalid offer price value.'}, status=400)

            new_discount = None
            if raw_discount is not None and str(raw_discount).strip() != '':
                try:
                    new_discount = int(float(str(raw_discount)))
                    if new_discount < 0 or new_discount > 100:
                        return JsonResponse({'success': False, 'error': 'Discount percentage must be between 0 and 100.'}, status=400)
                except ValueError:
                    pass

            # If offer price is not specified but discount percentage is given, calculate offer price
            if new_offer_price is None and new_discount is not None and new_discount > 0:
                disc_decimal = Decimal(str(new_discount))
                calc_offer = new_price - (new_price * disc_decimal / Decimal('100'))
                new_offer_price = calc_offer.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Build target queryset
            if update_all_matching and search_term:
                filter_query = Q()
                if match_type == 'exact':
                    filter_query &= Q(sku__iexact=search_term)
                elif match_type == 'startswith':
                    filter_query &= Q(sku__istartswith=search_term)
                else:
                    filter_query &= (Q(sku__icontains=search_term) | Q(name__icontains=search_term))

                if category_id:
                    try:
                        filter_query &= Q(categories__id=int(category_id))
                    except ValueError:
                        pass
                target_products = Product.objects.filter(filter_query)
            elif product_ids:
                if isinstance(product_ids, str):
                    product_ids = [int(i.strip()) for i in product_ids.split(',') if i.strip()]
                target_products = Product.objects.filter(id__in=product_ids)
            else:
                return JsonResponse({'success': False, 'error': 'No products selected for price update.'}, status=400)

            updated_count = 0
            with transaction.atomic():
                for p in target_products:
                    p.price = new_price
                    if new_offer_price is not None:
                        p.offer_price = new_offer_price
                        if new_price > Decimal('0'):
                            calc_disc = ((new_price - new_offer_price) / new_price) * Decimal('100')
                            p.discount_percentage = int(calc_disc.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                        else:
                            p.discount_percentage = 0
                    else:
                        p.offer_price = new_price
                        p.discount_percentage = 0
                    p.save()
                    updated_count += 1

            return JsonResponse({
                'success': True,
                'count': updated_count,
                'new_price': float(new_price),
                'new_offer_price': float(new_offer_price if new_offer_price is not None else new_price),
                'message': f'Successfully updated price for {updated_count} product(s) to ₹{new_price:,.2f}!'
            })

        except Exception as e:
            logger.exception('Batch price update failed')
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    def quick_update_single_view(self, request):
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

        try:
            data = json.loads(request.body.decode('utf-8'))
            product_id = data.get('product_id')
            raw_price = data.get('price')
            raw_offer = data.get('offer_price')

            product = get_object_or_404(Product, id=product_id)

            if raw_price is None or str(raw_price).strip() == '':
                return JsonResponse({'success': False, 'error': 'Price cannot be empty.'}, status=400)

            new_price = Decimal(str(raw_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if new_price <= Decimal('0'):
                return JsonResponse({'success': False, 'error': 'Price must be greater than zero.'}, status=400)

            product.price = new_price

            if raw_offer is not None and str(raw_offer).strip() != '':
                new_offer = Decimal(str(raw_offer)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if new_offer > new_price:
                    return JsonResponse({'success': False, 'error': 'Offer price cannot exceed regular price.'}, status=400)
                product.offer_price = new_offer
                if new_price > Decimal('0'):
                    calc_disc = ((new_price - new_offer) / new_price) * Decimal('100')
                    product.discount_percentage = int(calc_disc.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            else:
                product.offer_price = new_price
                product.discount_percentage = 0

            product.save()

            return JsonResponse({
                'success': True,
                'product_id': product.id,
                'price': float(product.price),
                'offer_price': float(product.offer_price),
                'discount_percentage': product.discount_percentage,
                'message': f'Updated {product.name} (SKU: {product.sku}) to ₹{product.price:,.2f}'
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
