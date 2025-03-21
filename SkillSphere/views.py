from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.generic import TemplateView

from accounts.forms import ContactForm
from accounts.models import Feedback
from classes.models import Class


class CoverPageView(TemplateView):
    template_name = "index.html"
    model = Class
    context_object_name = 'class_obj'


def feedback_create(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)  # Create form instance with POST data
        if form.is_valid():
            instance = form.save(commit=False)
            instance.save()
            messages.success(request, 'Feedback Sent successfully!')
            print('Feedback Sent successfully!')
            return redirect('cover_page')
    else:
        form = ContactForm()  # Create an empty form instance for GET requests
    objs = (Feedback.objects.all())

    context = {'form': form,
               'feedbacks': objs, }
    return render(request, 'index.html', context)
