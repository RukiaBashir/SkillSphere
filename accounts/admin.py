from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import SiteConfiguration, SkillUser, Feedback


class CustomUserAdmin(UserAdmin):
    model = SkillUser
    list_display = ('username', 'first_name', 'last_name', 'role', 'instructor_status', 'is_staff')
    list_filter = ('role', 'instructor_status', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        (None,
         {'fields': ('role', 'instructor_status', 'specialization', 'birth_date', 'phone_number', 'profile_image')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None,
         {'fields': ('role', 'instructor_status', 'specialization', 'birth_date', 'phone_number', 'profile_image')}),
    )
    search_fields = ('username', 'first_name', 'last_name', 'role')
    ordering = ('username',)


class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('f_name', 'f_email', 'timestamp')
    search_fields = ('f_name', 'f_email', 'f_message')


admin.site.register(SiteConfiguration)
admin.site.register(SkillUser, CustomUserAdmin)
admin.site.register(Feedback, FeedbackAdmin)
