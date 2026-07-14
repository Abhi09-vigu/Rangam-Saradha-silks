from django.contrib.admin import AdminSite
from django.db.models import Sum
from django.utils import timezone
import datetime

class CustomAdminSite(AdminSite):
    site_header = "Rangam Saradha Silk Sarees Admin"
    site_title = "Merchant Control Center"
    index_title = "Dashboard Statistics"

    def logout(self, request, extra_context=None):
        from django.contrib.auth import logout
        from django.shortcuts import redirect
        logout(request)
        return redirect('admin:login')

    def index(self, request, extra_context=None):
        from shop.models import Order, Product, Category, Coupon
        from accounts.models import CustomUser

        extra_context = extra_context or {}

        # 1. Calc statistics
        today = timezone.now().date()
        orders_today = Order.objects.filter(created_at__date=today)
        extra_context['orders_today_count'] = orders_today.count()
        
        revenue_today = orders_today.exclude(order_status='CANCELLED').aggregate(sum_revenue=Sum('grand_total'))['sum_revenue'] or 0.00
        extra_context['revenue_today'] = revenue_today

        extra_context['total_products'] = Product.objects.count()
        extra_context['total_customers'] = CustomUser.objects.filter(is_staff=False).count()
        extra_context['total_categories'] = Category.objects.count()
        extra_context['total_coupons'] = Coupon.objects.count()

        # 2. Inventory warnings (low stock <= 5)
        extra_context['low_stock_products'] = Product.objects.filter(stock__lte=5, is_active=True).order_by('stock')[:5]

        # 3. Recent orders & customers
        extra_context['recent_orders'] = Order.objects.order_by('-created_at')[:5]
        extra_context['recent_customers'] = CustomUser.objects.filter(is_staff=False).order_by('-date_joined')[:5]

        # 4. Sales graph (last 7 days)
        sales_data = []
        sales_labels = []
        for i in range(6, -1, -1):
            day = today - datetime.timedelta(days=i)
            day_orders = Order.objects.filter(created_at__date=day).exclude(order_status='CANCELLED')
            day_revenue = day_orders.aggregate(sum_rev=Sum('grand_total'))['sum_rev'] or 0.00
            sales_data.append(float(day_revenue))
            sales_labels.append(day.strftime('%b %d'))
            
        extra_context['sales_data'] = sales_data
        extra_context['sales_labels'] = sales_labels

        return super().index(request, extra_context)

custom_admin_site = CustomAdminSite(name='custom_admin')
