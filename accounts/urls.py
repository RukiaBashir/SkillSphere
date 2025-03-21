from django.urls import path
from .views import register, verify_otp, login_view, logout_view, \
    UserProfileUpdateView, forgot_password, LearnerDashboardView, \
    InstructorDashboardView, InstructorPaymentSuccessView, BecomeInstructorView  # , login_view, logout_view, profile

app_name = 'accounts'

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', UserProfileUpdateView.as_view(), name='profile'),
    path('forgot-password/', forgot_password, name='forgot_password'),
    path("become-instructor/", BecomeInstructorView.as_view(), name="become-instructor"),
    path("payment-success/", InstructorPaymentSuccessView.as_view(), name="payment-success"),
    path('dashboard/', LearnerDashboardView.as_view(), name='learner-dashboard'),
    path("dashboard/", InstructorDashboardView.as_view(), name="instructor-dashboard"),
    path('verify-otp/', verify_otp, name='verify_otp'),

]