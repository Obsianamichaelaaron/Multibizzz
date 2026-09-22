from django.contrib import admin
from .models import CMSSection, CMSContent, CMSHeroSlide, CMSBrand, CMSTestimonial, CMSNews, ContactInquiry, ContactReply

@admin.register(CMSHeroSlide)
class CMSHeroSlideAdmin(admin.ModelAdmin):
    list_display = ('title', 'sort_order', 'is_active', 'created_at')
    list_editable = ('sort_order', 'is_active')

@admin.register(CMSBrand)
class CMSBrandAdmin(admin.ModelAdmin):
    list_display = ('brand_name', 'brand_category', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')

@admin.register(CMSTestimonial)
class CMSTestimonialAdmin(admin.ModelAdmin):
    list_display = ('author_name', 'company', 'rating', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')

@admin.register(CMSNews)
class CMSNewsAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'news_date', 'is_featured', 'is_active')
    list_filter = ('is_featured', 'is_active', 'category')

@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'status', 'is_read', 'created_at')
    list_filter = ('status', 'is_read', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')

@admin.register(ContactReply)
class ContactReplyAdmin(admin.ModelAdmin):
    list_display = ('inquiry', 'admin', 'sent_at', 'email_sent')
