from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import DeleteView

from payments.models import CartItem
from .forms import ClassForm, SkillCategoryForm
from .models import Class, SkillCategory, Enrollment


def class_list(request):
    classes = Class.objects.all()
    purchased_class_ids = []
    own_class_ids = []
    if request.user.is_authenticated:
        if request.user.role == 'learner':
            # Collect IDs of classes the learner has purchased (is_paid=True)
            purchased_class_ids = list(
                request.user.enrollments.filter(is_paid=True).values_list('class_obj__id', flat=True)
            )
        elif request.user.role == 'instructor':
            # Collect IDs of classes created by the instructor
            own_class_ids = list(
                Class.objects.filter(instructor=request.user).values_list('id', flat=True)
            )
    context = {
        'classes': classes,
        'purchased_class_ids': purchased_class_ids,
        'own_class_ids': own_class_ids,
    }
    return render(request, 'class_list.html', context)


def class_detail(request, pk):
    class_obj = get_object_or_404(Class, pk=pk)
    purchased = False
    # If a learner is logged in, check if they have purchased/enrolled (with is_paid=True) in the class
    if request.user.is_authenticated and request.user.role == 'learner':
        purchased = Enrollment.objects.filter(
            learner=request.user,
            class_obj=class_obj,
            is_paid=True
        ).exists()

    context = {
        'class_obj': class_obj,
        'purchased': purchased,
    }
    return render(request, 'class_detail.html', context)


# Create a new class (for instructors only)


@login_required
def class_create(request):
    """
    Allow only paid instructors (or admin) to create classes.
    If an instructor hasn't paid, redirect them to the instructor registration page.
    """
    if request.user.role != 'instructor' and not request.user.is_superuser:
        messages.error(request, "You are not authorized to create a class.")
        return redirect('classes:class-list')

    # Admins can create classes freely
    if not request.user.is_superuser:
        instructor_payment = CartItem.objects.filter(
            user=request.user,
            class_booking__isnull=True,  # Instructor registration fee
            payment_status='completed'
        ).exists()

        if not instructor_payment:
            messages.warning(request, "You must complete instructor registration before creating a class.")
            return redirect('accounts:become-instructor')  # Redirect to instructor registration page

    if request.method == 'POST':
        form = ClassForm(request.POST, request.FILES)
        if form.is_valid():
            new_class = form.save(commit=False)
            new_class.instructor = request.user  # Auto-assign current user as instructor
            new_class.save()
            messages.success(request, "Class created successfully.")
            return redirect('classes:class-detail', pk=new_class.pk)
    else:
        form = ClassForm()

    return render(request, 'class_form.html', {'form': form})
class ClassDeleteView(LoginRequiredMixin, DeleteView):
    model = Class
    template_name = 'classes/class_confirm_delete.html'
    success_url = reverse_lazy('classes:class-list')

    def get_queryset(self):
        # Allow deletion only if the current user is the instructor for this class.
        return Class.objects.filter(instructor=self.request.user)


# Update an existing class (for instructors only)
@login_required
def class_update(request, pk):
    class_obj = get_object_or_404(Class, pk=pk)
    if request.user.role != 'instructor' or class_obj.instructor != request.user:
        messages.error(request, "You are not authorized to update this class.")
        return redirect('classes:class-detail', pk=pk)

    if request.method == 'POST':
        form = ClassForm(request.POST, request.FILES, instance=class_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Class updated successfully.")
            return redirect('classes:class-detail', pk=class_obj.pk)
    else:
        form = ClassForm(instance=class_obj)

    return render(request, 'classes/class_update.html', {'form': form, 'class_obj': class_obj})


# Instructor dashboard to manage classes
@login_required
def dashboard(request):
    if request.user.role != 'instructor':
        messages.error(request, "Access restricted to instructors only.")
        return redirect('classes:class-list')

    # List only classes created by the instructor
    classes_created = Class.objects.filter(instructor=request.user)
    context = {
        'classes_created': classes_created,
    }
    return render(request, 'classes/dashboard.html', context)


# List of skill categories
def skillcategory_list(request):
    categories = SkillCategory.objects.all()
    return render(request, 'skillcategory_list.html', {'categories': categories})


# Create a new skill category (for instructors only)
@login_required
def skillcategory_create(request):
    if request.user.role != 'instructor':
        messages.error(request, "You are not authorized to create a skill category.")
        return redirect('classes:skillcategory-list')

    if request.method == 'POST':
        form = SkillCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Skill category created successfully.")
            return redirect('classes:skillcategory-list')
    else:
        form = SkillCategoryForm()

    return render(request, 'skillcategory_form.html', {'form': form})


class SkillCategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = SkillCategory
    template_name = 'classes/skillcategory_confirm_delete.html'
    success_url = reverse_lazy('classes:skillcategory-list')


# List enrollments (for managing enrollments)
@login_required
def enrollment_list(request):
    if request.user.role == 'instructor':
        # Get classes created by the instructor
        classes_taught = Class.objects.filter(instructor=request.user)
        enrollments = Enrollment.objects.filter(class_obj__in=classes_taught).select_related('learner')
    elif request.user.role == 'learner':
        # Show only paid enrollments for learners
        enrollments = Enrollment.objects.filter(learner=request.user, is_paid=True)
    else:
        enrollments = Enrollment.objects.none()

    return render(request, 'classes/enrollment_list.html', {'enrollments': enrollments})


@login_required
def update_learning_stage(request, enrollment_id):
    if request.method == "POST" and request.user.role == "instructor":
        enrollment = get_object_or_404(Enrollment, id=enrollment_id, class_obj__instructor=request.user)
        new_stage = request.POST.get("learning_stage")
        if new_stage in dict(Enrollment.LEARNING_STAGE_CHOICES):
            enrollment.learning_stage = new_stage
            enrollment.save()
            messages.success(request, "Learner's progress updated successfully.")
        else:
            messages.error(request, "Invalid learning stage.")
    return redirect("classes:enrollment_list")
