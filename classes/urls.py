from django.urls import path
from . import views
from .views import SkillCategoryDeleteView, ClassDeleteView, SkillCategoryUpdateView

app_name = 'classes'

urlpatterns = [
    # List all available classes
    path('class/', views.class_list, name='class-list'),

    # Detail view for a specific class
    path('class/<int:pk>/', views.class_detail, name='class-detail'),

    # Create a new class (for instructors)
    path('create/', views.class_create, name='class-create'),

    # Update an existing class (for instructors)
    path('class/<int:pk>/update/', views.class_update, name='class-update'),

    # Delete a class (for instructors)
    path('class/<int:pk>/delete/', ClassDeleteView.as_view(), name='class-delete'),

    # Instructor dashboard to manage classes
    path('class/dashboard/', views.dashboard, name='dashboard'),

    # List of skill categories
    path('class/skillcategories/', views.skillcategory_list, name='skillcategory-list'),
    path('class/skillcategories/<int:pk>/update/', SkillCategoryUpdateView.as_view(), name='skillcategory-update'),
    path('class/skillcategories/<int:pk>/delete/', SkillCategoryDeleteView.as_view(), name='skillcategory-delete'),

    # Create a new skill category
    path('class/skillcategories/create/', views.skillcategory_create, name='skillcategory-create'),

    # List enrollments (for managing enrollments)
    path('enrollments/', views.enrollment_list, name='enrollment-list'),
    path('enrollment/<int:enrollment_id>/update/', views.update_learning_stage, name='update_learning_stage'),
]
