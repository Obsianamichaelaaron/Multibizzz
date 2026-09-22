from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.conf import settings

from .models import CMSHeroSlide, CMSBrand, CMSTestimonial, CMSNews, CMSSection, CMSContent, ContactInquiry, ContactReply
from audit.utils import get_client_ip, log_audit
from accounts.decorators import admin_required

def home(request):
    """Public Landing Page (index.php equivalent)."""
    from jobs.models import JobPosting
    
    hero_slides = CMSHeroSlide.objects.filter(is_active=True).order_by('sort_order')
    brands = CMSBrand.objects.filter(is_active=True).order_by('sort_order')
    testimonials = CMSTestimonial.objects.filter(is_active=True).order_by('sort_order')
    featured_news = CMSNews.objects.filter(is_active=True, is_featured=True)[:3]
    featured_jobs = JobPosting.objects.filter(status='active').order_by('-posted_at')[:6]

    # Quick contact form handler on homepage
    if request.method == 'POST' and 'contact_submit' in request.POST:
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', 'General Inquiry').strip()
        message_text = request.POST.get('message', '').strip()

        if name and email and message_text:
            inquiry = ContactInquiry.objects.create(
                name=name,
                email=email,
                subject=subject,
                message=message_text,
                ip_address=get_client_ip(request)
            )
            log_audit(
                request,
                'submit_contact_inquiry',
                f"Contact inquiry submitted by {name} ({email}): '{subject}'",
                target_type='inquiry',
                target_id=inquiry.id,
                target_name=subject
            )
            messages.success(request, "Thank you for reaching out! We will get back to you shortly.")
            return redirect('home')

    return render(request, 'core/home.html', {
        'hero_slides': hero_slides,
        'brands': brands,
        'testimonials': testimonials,
        'featured_news': featured_news,
        'featured_jobs': featured_jobs,
    })


def about(request):
    """About Multibiz page."""
    brands = CMSBrand.objects.filter(is_active=True).order_by('sort_order')
    testimonials = CMSTestimonial.objects.filter(is_active=True).order_by('sort_order')
    return render(request, 'core/about.html', {
        'brands': brands,
        'testimonials': testimonials,
    })


def services(request):
    """Services showcase page."""
    return render(request, 'core/services.html')


def solutions(request):
    """Solutions page."""
    return render(request, 'core/solutions.html')


def privacy_policy(request):
    """Public privacy policy page."""
    return render(request, 'core/policy.html', {
        'policy_type': 'privacy',
        'policy_title': 'Privacy Policy',
        'policy_updated': 'September 17, 2026',
    })


def terms_conditions(request):
    """Public terms and conditions page."""
    return render(request, 'core/policy.html', {
        'policy_type': 'terms',
        'policy_title': 'Terms and Conditions',
        'policy_updated': 'September 17, 2026',
    })


def cookie_policy(request):
    """Public cookie policy page."""
    return render(request, 'core/policy.html', {
        'policy_type': 'cookies',
        'policy_title': 'Cookie Policy',
        'policy_updated': 'September 17, 2026',
    })


@require_POST
def contact_submit_ajax(request):
    """AJAX endpoint for contact form submissions."""
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    subject = request.POST.get('subject', 'General Inquiry').strip()
    message = request.POST.get('message', '').strip()

    if not name or not email or not message:
        return JsonResponse({'success': False, 'message': 'Please complete all required fields.'})

    inquiry = ContactInquiry.objects.create(
        name=name,
        email=email,
        subject=subject,
        message=message,
        ip_address=get_client_ip(request)
    )

    log_audit(
        request,
        'submit_contact_inquiry',
        f"Contact inquiry submitted by {name} ({email}): '{subject}'",
        target_type='inquiry',
        target_id=inquiry.id,
        target_name=subject
    )

    return JsonResponse({
        'success': True,
        'message': 'Your message has been sent successfully. Our team will contact you soon!'
    })


# ==========================================
# ADMIN CMS & INQUIRIES MANAGEMENT
# ==========================================

@admin_required
def admin_cms(request):
    """Content Management System dashboard."""
    slides = CMSHeroSlide.objects.all().order_by('sort_order')
    brands = CMSBrand.objects.all().order_by('sort_order')
    testimonials = CMSTestimonial.objects.all().order_by('sort_order')
    news_articles = CMSNews.objects.all().order_by('-created_at')

    # Add new slide
    if request.method == 'POST' and 'add_slide' in request.POST:
        title = request.POST.get('title')
        subtitle = request.POST.get('subtitle')
        btn_text = request.POST.get('button_text', 'Learn More')
        btn_link = request.POST.get('button_link', '#')
        img_path = request.POST.get('image_path', '')
        CMSHeroSlide.objects.create(
            title=title,
            subtitle=subtitle,
            button_text=btn_text,
            button_link=btn_link,
            image_path=img_path
        )
        log_audit(request, 'create_cms_slide', f'Added hero slide: {title}', target_type='cms')
        messages.success(request, "Hero slide created successfully!")
        return redirect('admin_cms')

    # Add new brand
    if request.method == 'POST' and 'add_brand' in request.POST:
        brand_name = request.POST.get('brand_name')
        desc = request.POST.get('brand_description')
        logo = request.POST.get('brand_logo')
        CMSBrand.objects.create(
            brand_name=brand_name,
            brand_description=desc,
            brand_logo=logo
        )
        log_audit(request, 'create_cms_brand', f'Added brand: {brand_name}', target_type='cms')
        messages.success(request, "Brand added successfully!")
        return redirect('admin_cms')

    # Add new testimonial
    if request.method == 'POST' and 'add_testimonial' in request.POST:
        author = request.POST.get('author_name')
        company = request.POST.get('company')
        role = request.POST.get('author_role', '')
        content = request.POST.get('content')
        rating = int(request.POST.get('rating', 5))
        CMSTestimonial.objects.create(
            author_name=author,
            company=company,
            author_role=role,
            content=content,
            rating=rating
        )
        log_audit(request, 'create_cms_testimonial', f'Added testimonial by {author}', target_type='cms')
        messages.success(request, "Testimonial added successfully!")
        return redirect('admin_cms')

    # Add new news article
    if request.method == 'POST' and 'add_news' in request.POST:
        title = request.POST.get('title')
        category = request.POST.get('category', 'Announcements')
        excerpt = request.POST.get('excerpt', '')
        content = request.POST.get('content', '')
        news_date = request.POST.get('news_date')
        is_featured = bool(request.POST.get('is_featured'))
        
        from django.utils import timezone
        if not news_date:
            news_date = timezone.now().date()
            
        CMSNews.objects.create(
            title=title,
            category=category,
            excerpt=excerpt,
            content=content,
            news_date=news_date,
            is_featured=is_featured
        )
        log_audit(request, 'create_cms_news', f'Added news article: {title}', target_type='cms')
        messages.success(request, "News article published successfully!")
        return redirect('admin_cms')

    return render(request, 'admin/cms.html', {
        'slides': slides,
        'brands': brands,
        'testimonials': testimonials,
        'news_articles': news_articles,
    })


@admin_required
def admin_cms_delete_item(request, item_type, item_id):
    """Deletes a CMS entity."""
    if item_type == 'slide':
        item = get_object_or_404(CMSHeroSlide, pk=item_id)
    elif item_type == 'brand':
        item = get_object_or_404(CMSBrand, pk=item_id)
    elif item_type == 'testimonial':
        item = get_object_or_404(CMSTestimonial, pk=item_id)
    elif item_type == 'news':
        item = get_object_or_404(CMSNews, pk=item_id)
    else:
        messages.error(request, "Invalid CMS item type.")
        return redirect('admin_cms')

    item_name = str(item)
    item.delete()
    log_audit(request, f'delete_cms_{item_type}', f'Deleted {item_type}: {item_name}', target_type='cms')
    messages.success(request, f"{item_type.capitalize()} deleted successfully!")
    return redirect('admin_cms')


@admin_required
def admin_inquiries(request):
    """Inquiries inbox for administrator."""
    inquiries = ContactInquiry.objects.all().order_by('-created_at')

    if request.method == 'POST' and 'reply_inquiry' in request.POST:
        inquiry_id = request.POST.get('inquiry_id')
        reply_text = request.POST.get('reply_text', '').strip()
        inquiry = get_object_or_404(ContactInquiry, pk=inquiry_id)

        if reply_text:
            ContactReply.objects.create(
                inquiry=inquiry,
                admin=request.user,
                reply_text=reply_text,
                email_sent=True
            )
            inquiry.status = 'replied'
            inquiry.is_read = True
            inquiry.save()

            log_audit(request, 'reply_contact_inquiry', f'Replied to inquiry #{inquiry.id} from {inquiry.email}', target_type='inquiry', target_id=inquiry.id)
            messages.success(request, f"Reply recorded for {inquiry.name}!")
            return redirect('admin_inquiries')

    return render(request, 'admin/inquiries.html', {'inquiries': inquiries})
