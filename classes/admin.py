from django.contrib import admin

from .models import Class


class ClassAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'status', 'is_approved')  # Removed 'created_at'
    list_filter = ('status', 'is_approved', 'category')
    search_fields = ('title', 'instructor__username')


admin.site.register(Class, ClassAdmin)
