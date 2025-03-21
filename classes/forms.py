from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from classes.models import Class
from .models import SkillCategory


class SkillCategoryForm(forms.ModelForm):
    class Meta:
        model = SkillCategory
        fields = ['name', 'description']


class SkillCategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = SkillCategory
    form_class = SkillCategoryForm
    template_name = 'classes/skillcategory_update.html'
    success_url = reverse_lazy('classes:skillcategory-list')


class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        # Removed 'instructor' so it's set automatically in the view
        fields = [
            'category',      # Replaces 'skill_category'
            'title',
            'description',
            'price',
            'schedule',
            'venue_address', # New field added
            'image'          # For the thumbnail
        ]
        widgets = {
            'schedule': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }