from django import forms
from django.utils.timezone import now

from classes.models import Class
from .models import SkillCategory


from django import forms
from django.utils.timezone import now
from .models import Class

class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        # Removed 'instructor' so it's set in the view
        fields = [
            'category',           # Category of the class
            'title',              # Title of the class
            'description',        # Description of the class
            'price',              # Price of the class
            'schedule',           # Schedule (date and time)
            'venue_address',      # Location of the class
            'local_image',        # Local file upload (used for Supabase)
            'external_image_url', # Supabase/public URL
        ]
        widgets = {
            'schedule': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'min': now().strftime('%Y-%m-%dT%H:%M'),
                    'class': 'form-control'
                }
            ),
            'external_image_url': forms.HiddenInput(),  # You can also make it read-only instead
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['local_image'].required = False
        self.fields['external_image_url'].required = False


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
