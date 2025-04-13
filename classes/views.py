from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import DeleteView, UpdateView

from SkillSphere.utils.supabase_upload import upload_to_supabase
from payments.models import CartItem
from .forms import ClassForm, SkillCategoryForm
from .models import Class, SkillCategory, Enrollment


def class_list(request):
    classes = Class.objects.all()
    purchased_class_ids = []
    own_class_ids = []

    if request.user.is_authenticated:
        if request.user.role == 'learner':
            # Learner's paid classes
            purchased_class_ids = list(
                request.user.enrollments.filter(is_paid=True).values_list('class_obj__id', flat=True)
            )
        elif request.user.role == 'instructor':
            # Instructor's own classes
            own_class_ids = list(
                Class.objects.filter(instructor=request.user).values_list('id', flat=True)
            )

    # Annotate visibility
    for class_obj in classes:
        class_obj.show_details = (
                request.user.is_superuser or
                class_obj.id in purchased_class_ids or
                class_obj.id in own_class_ids
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
def image_upload_preview(request):
    public_url = None

    if request.method == 'POST':
        image_file = request.FILES.get('image')
        if image_file:
            try:
                content_type = image_file.content_type
                public_url = upload_to_supabase(
                    image_file,
                    folder='test_uploads',
                    filename=image_file.name,
                    content_type=content_type
                )
                messages.success(request, "Image uploaded successfully.")
            except Exception as e:
                messages.error(request, f"Upload failed: {e}")

    return render(request, 'classes/image_upload_preview.html', {'public_url': public_url})


@login_required
def class_create(request):
    if request.user.role != 'instructor':
        messages.error(request, "Only instructors can create classes.")
        return redirect('classes:class-list')

    if request.method == 'POST':
        form = ClassForm(request.POST, request.FILES)
        if form.is_valid():
            new_class = form.save(commit=False)
            new_class.instructor = request.user  # assign instructor

            image_file = request.FILES.get('local_image')
            if image_file:
                try:
                    content_type = image_file.content_type
                    public_url = upload_to_supabase(
                        image_file,
                        folder='class_thumbnails',
                        filename=image_file.name,
                        content_type=content_type
                    )
                    new_class.external_image_url = public_url
                    new_class.local_image = None
                    messages.success(request, "Image uploaded successfully.")
                except Exception as e:
                    messages.error(request, f"Image upload to Supabase failed: {e}")
            else:
                messages.info(request, "No image uploaded.")

            new_class.save()
            messages.success(request, "Class created successfully.")
            return redirect('classes:class-detail', pk=new_class.pk)
    else:
        form = ClassForm()

    return render(request, 'classes/class_create.html', {'form': form})


class ClassDeleteView(LoginRequiredMixin, DeleteView):
    model = Class
    template_name = 'class_delete.html'
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
            updated_class = form.save(commit=False)

            image_file = request.FILES.get('local_image')
            if image_file:
                try:
                    content_type = image_file.content_type
                    public_url = upload_to_supabase(
                        image_file,
                        folder='class_thumbnails',
                        filename=image_file.name,
                        content_type=content_type
                    )
                    updated_class.external_image_url = public_url
                    updated_class.local_image = None
                    messages.success(request, "Image uploaded successfully.")
                except Exception as e:
                    messages.error(request, f"Image upload to Supabase failed: {e}")
            else:
                messages.info(request, "No new image uploaded.")

            updated_class.save()
            messages.success(request, "Class updated successfully.")
            return redirect('classes:class-detail', pk=updated_class.pk)
    else:
        form = ClassForm(instance=class_obj)

    return render(request, 'classes/class_update.html', {'form': form, 'class_obj': class_obj})


# Instructor dashboard to manage classes


@login_required
def dashboard(request):
    if request.user.role != 'instructor':
        messages.error(request, "Access restricted to instructors only.")
        return redirect('classes:class-list')

    # Retrieve all classes created by the instructor.
    classes_created = Class.objects.filter(instructor=request.user)

    # Summary statistics:
    total_classes = classes_created.count()
    ongoing_classes = classes_created.filter(status='ongoing').count()  # Assumes Class.status exists
    coming_soon_classes = classes_created.filter(status='coming_soon').count()  # Assumes status field
    learners_count = CartItem.objects.filter(
        class_booking__in=classes_created,
        payment_status='completed'
    ).values('user').distinct().count()

    # Check if the instructor has completed the registration fee.
    instructor_paid = CartItem.objects.filter(
        user=request.user,
        class_booking__isnull=True,
        payment_status='completed'
    ).exists()

    context = {
        'classes_created': classes_created,
        'total_classes': total_classes,
        'ongoing_classes': ongoing_classes,
        'coming_soon_classes': coming_soon_classes,
        'learners_count': learners_count,
        'instructor_paid': instructor_paid,
    }
    return render(request, 'classes/dashboard.html', context)


# List of skill categories
def skillcategory_list(request):
    categories = SkillCategory.objects.all()

    # Pass additional info to each category for permission checks in the template.
    for category in categories:
        category.can_edit = (
                request.user.is_authenticated and
                request.user.role == 'instructor' and
                category.created_by == request.user
        )
        # This assumes your related model (e.g. Class) uses related_name='classes'
        category.has_classes = category.classes.exists()

    return render(request, 'skillcategory_list.html', {'categories': categories})


# Create a new skill category (for instructors only)
def skillcategory_create(request):
    if request.method == 'POST':
        form = SkillCategoryForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('classes:skillcategory-list')
    else:
        form = SkillCategoryForm(user=request.user)

    return render(request, 'skillcategory_form.html', {'form': form})


class SkillCategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = SkillCategory
    form_class = SkillCategoryForm
    template_name = 'classes/skillcategory_update.html'
    success_url = reverse_lazy('classes:skillcategory-list')

    def get_queryset(self):
        qs = super().get_queryset()
        # Only allow instructors to edit categories they created.
        if self.request.user.role == 'instructor':
            return qs.filter(created_by=self.request.user)
        return qs.none()


class SkillCategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = SkillCategory
    template_name = 'classes/skillcategory_confirm_delete.html'
    success_url = reverse_lazy('classes:skillcategory-list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.has_classes():
            messages.error(request, "Cannot delete this category because it has associated classes.")
            return redirect(self.success_url)
        return super().delete(request, *args, **kwargs)


# List enrollments (for managing enrollments)
@login_required
def enrollment_list(request):
    enrollments = Enrollment.objects.none()

    if request.user.role == 'instructor':
        # Get classes created by the instructor and associated enrollments
        classes_taught = Class.objects.filter(instructor=request.user)
        enrollments = Enrollment.objects.filter(class_obj__in=classes_taught).select_related('learner', 'class_obj')

    elif request.user.role == 'learner':
        # Display only paid enrollments for learners
        enrollments = Enrollment.objects.filter(learner=request.user, is_paid=True).select_related('class_obj')

    return render(request, 'classes/enrollment_list.html', {'enrollments': enrollments})


@login_required
def update_learning_stage(request, enrollment_id):
    if request.method == "POST" and request.user.role == "instructor":
        enrollment = get_object_or_404(Enrollment, id=enrollment_id, class_obj__instructor=request.user)

        # Update learning stage
        new_stage = request.POST.get("learning_stage")
        if new_stage in dict(Enrollment.LEARNING_STAGE_CHOICES):
            enrollment.learning_stage = new_stage
        else:
            messages.error(request, "Invalid learning stage.")
            return redirect("classes:enrollment-list")

        # Update progress and ensure it's within a valid range
        try:
            new_progress = int(request.POST.get("progress", enrollment.progress))
            if 0 <= new_progress <= 100:
                enrollment.progress = new_progress
            else:
                messages.error(request, "Invalid progress value. Must be between 0 and 100.")
                return redirect("classes:enrollment-list")
        except (ValueError, TypeError):
            messages.error(request, "Progress must be a valid number.")
            return redirect("classes:enrollment-list")

        enrollment.save()
        messages.success(request, "Learner's progress updated successfully.")

    return redirect("classes:enrollment-list")
