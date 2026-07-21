from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import HeroSlider, OfferBanner, Testimonial, CMSPage, FAQ, InstagramPost, ContactSubmission, BudgetRange, WhyChooseUs
from shop.models import Category, Product, Collection

def index(request):
    sliders = HeroSlider.objects.filter(is_active=True).order_by('display_order')
    categories = Category.objects.filter(is_active=True).order_by('display_order')[:6]
    budget_ranges = BudgetRange.objects.filter(is_active=True).order_by('display_order')
    
    # Dynamic Homepage Product Sections
    featured_products = Product.objects.filter(is_active=True, is_featured=True).prefetch_related('images', 'categories')[:4]
    trending_products = Product.objects.filter(is_active=True, is_trending=True).prefetch_related('images', 'categories')[:4]
    new_arrivals = Product.objects.filter(is_active=True, is_new_arrival=True).prefetch_related('images', 'categories')[:4]
    best_sellers = Product.objects.filter(is_active=True, is_best_seller=True).prefetch_related('images', 'categories')[:4]
    today_deals = Product.objects.filter(is_active=True, is_today_deal=True).prefetch_related('images', 'categories')[:12]
    
    # Featured Collections and Why Choose Us
    featured_collections = Collection.objects.filter(is_active=True)[:4]
    why_choose_us = WhyChooseUs.objects.filter(is_active=True).order_by('display_order')

    # Offer Banners
    banners = OfferBanner.objects.filter(is_active=True).order_by('display_order')[:3]
    
    # Testimonials
    testimonials = Testimonial.objects.filter(is_active=True)[:5]
    
    # Instagram gallery
    insta_posts = InstagramPost.objects.filter(is_active=True).order_by('display_order')[:6]
    
    # FAQ list for homepage
    faqs = FAQ.objects.filter(is_active=True)[:4]

    # Recently viewed products placeholder (fetched from cookie/session)
    recent_ids = request.session.get('recently_viewed', [])
    recently_viewed = Product.objects.filter(id__in=recent_ids, is_active=True).prefetch_related('images')[:4]

    context = {
        'sliders': sliders,
        'categories': categories,
        'budget_ranges': budget_ranges,
        'featured_products': featured_products,
        'trending_products': trending_products,
        'new_arrivals': new_arrivals,
        'best_sellers': best_sellers,
        'today_deals': today_deals,
        'featured_collections': featured_collections,
        'why_choose_us': why_choose_us,
        'banners': banners,
        'testimonials': testimonials,
        'insta_posts': insta_posts,
        'faqs': faqs,
        'recently_viewed': recently_viewed,
    }
    return render(request, 'home/index.html', context)

def cms_page_detail(request, slug):
    page = get_object_or_404(CMSPage, slug=slug)
    context = {'page': page}
    
    if slug == 'about-us':
        # Split content by the horizontal rule separator we seeded
        parts = page.content.split('<hr class="my-5" style="border-color: var(--border-color);">')
        if len(parts) >= 2:
            context['about_section_1'] = parts[0]
            context['about_section_2'] = parts[1]
        else:
            context['about_section_1'] = page.content
            context['about_section_2'] = ""
            
    return render(request, 'home/cms_page.html', context)

def faq_view(request):
    faqs = FAQ.objects.filter(is_active=True).order_by('display_order')
    return render(request, 'home/faq.html', {'faqs': faqs})

def contact_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        ContactSubmission.objects.create(
            name=name,
            email=email,
            subject=subject,
            message=message
        )
        messages.success(request, "Your message has been sent successfully! We will contact you shortly.")
        return redirect('home:contact')
        
    return render(request, 'home/contact.html')

def debug_db_view(request):
    if request.GET.get('key') != 'saradha123':
        from django.http import HttpResponse
        return HttpResponse("Unauthorized", status=401)
        
    from django.core.management import call_command
    from django.http import HttpResponse
    
    action = request.GET.get('action')
    log = ""
    if action == 'seed':
        try:
            call_command('loaddata', 'db_seed.json')
            log = "Database seeded successfully!"
        except Exception as e:
            log = f"Failed to seed: {str(e)}"
            
    pages = list(CMSPage.objects.values('id', 'title', 'slug'))
    categories = list(Category.objects.values('id', 'name', 'slug'))
    products = list(Product.objects.values('id', 'name', 'slug'))
    
    html = f"""
    <html>
    <body>
        <h1>Debug Database Dashboard</h1>
        <p><strong>Status:</strong> {log}</p>
        <form method="GET">
            <input type="hidden" name="key" value="saradha123">
            <button type="submit" name="action" value="seed">Run loaddata db_seed.json</button>
        </form>
        
        <h2>CMS Pages ({len(pages)})</h2>
        <pre>{pages}</pre>
        
        <h2>Categories ({len(categories)})</h2>
        <pre>{categories}</pre>
        
        <h2>Products ({len(products)})</h2>
        <pre>{products}</pre>
    </body>
    </html>
    """
    return HttpResponse(html)
