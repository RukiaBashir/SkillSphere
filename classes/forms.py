from django import forms
from django.utils.timezone import now

from classes.models import Class
from .models import SkillCategory


class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        # Removed 'instructor' so it's set automatically in the view
        fields = [
            'category',  # Replaces 'skill_category'
            'title',
            'description',
            'price',
            'schedule',
            'venue_address',  # New field added
           'local_image',# For the thumbnail
           'external_image_url',
  
        ]
        widgets = {
            'schedule': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'min': now().strftime('%Y-%m-%dT%H:%M')}
            ),
        }


class SkillCategoryForm(forms.ModelForm):
    class Meta:
        model = SkillCategory
        fields = ['name', 'description']

    def __init__(self, *args, **kwargs):
        # Capture the current user from the view.
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        # Only allow instructors to create or edit skills.
        if self.user and self.user.role != 'instructor':
            raise forms.ValidationError("You do not have permission to modify skills.")

        return cleaned_data

    def save(self, commit=True):
        skill_category = super().save(commit=False)
        # On creation, assign the current user as the creator.
        if not self.instance.pk:
            skill_category.created_by = self.user
        if commit:
            skill_category.save()
        return skill_category
