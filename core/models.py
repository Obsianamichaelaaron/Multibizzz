from django.db import models
from django.conf import settings

class CMSSection(models.Model):
    """Dynamic sections for the CMS."""
    CONTENT_TYPE_CHOICES = (
        ('text', 'Plain Text'),
        ('html', 'Rich HTML'),
        ('image', 'Single Image'),
        ('gallery', 'Gallery'),
        ('slider', 'Slider'),
    )
    section_key = models.CharField(max_length=100, unique=True)
    section_name = models.CharField(max_length=100)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, default='text')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.section_name} ({self.section_key})"


class CMSContent(models.Model):
    """Specific field keys and values within a CMS section."""
    section = models.ForeignKey(CMSSection, on_delete=models.CASCADE, related_name='contents')
    field_key = models.CharField(max_length=100)
    field_value = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=10, default='en')
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.section.section_key} - {self.field_key}"


class CMSHeroSlide(models.Model):
    """Hero carousel slides on the homepage."""
    title = models.CharField(max_length=255, blank=True, null=True)
    subtitle = models.TextField(blank=True, null=True)
    button_text = models.CharField(max_length=100, blank=True, null=True)
    button_link = models.CharField(max_length=255, blank=True, null=True)
    image = models.ImageField(upload_to='uploads/cms/', blank=True, null=True)
    image_path = models.CharField(max_length=255, blank=True, null=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.title or f"Slide #{self.pk}"


class CMSBrand(models.Model):
    """Partner and subsidiary brands showcased on landing/about pages."""
    brand_name = models.CharField(max_length=255)
    brand_description = models.TextField(blank=True, null=True)
    brand_overlay_title = models.CharField(max_length=255, blank=True, null=True)
    brand_overlay_description = models.TextField(blank=True, null=True)
    brand_logo = models.CharField(max_length=500, blank=True, null=True)
    brand_category = models.CharField(max_length=50, default='cor')
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.brand_name


class CMSTestimonial(models.Model):
    """Client and partner reviews/testimonials."""
    author_name = models.CharField(max_length=150)
    author_role = models.CharField(max_length=150, blank=True, null=True)
    company = models.CharField(max_length=150, blank=True, null=True)
    content = models.TextField()
    rating = models.IntegerField(default=5)
    image_path = models.CharField(max_length=255, blank=True, null=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.author_name} ({self.company})"


class CMSNews(models.Model):
    """News articles and announcements."""
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True, null=True)
    excerpt = models.TextField(blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    image_path = models.CharField(max_length=255, blank=True, null=True)
    news_date = models.DateField(blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    views = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-news_date', '-created_at']

    def __str__(self):
        return self.title


class ContactInquiry(models.Model):
    """Public contact form inquiries."""
    STATUS_CHOICES = (
        ('new', 'New'),
        ('open', 'Open / In Review'),
        ('replied', 'Replied'),
        ('closed', 'Closed'),
    )
    name = models.CharField(max_length=150)
    email = models.EmailField(max_length=255)
    subject = models.CharField(max_length=255, default='General Inquiry')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.status.upper()}] {self.name} - {self.subject}"


class ContactReply(models.Model):
    """Administrative replies to contact inquiries."""
    inquiry = models.ForeignKey(ContactInquiry, on_delete=models.CASCADE, related_name='replies')
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inquiry_replies'
    )
    reply_text = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    email_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"Reply to {self.inquiry.name} by {self.admin}"
