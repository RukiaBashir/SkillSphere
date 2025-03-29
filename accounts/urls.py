from django.urls import path
from .views import register, verify_otp, login_view, logout_view, \
    UserProfileUpdateView, forgot_password, LearnerDashboardView, \
    InstructorDashboardView, InstructorPaymentSuccessView, BecomeInstructorView, AdminDashboardView, request_otp, \
    dashboard_redirect, verify_otp_password, set_new_password

app_name = 'accounts'

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', UserProfileUpdateView.as_view(), name='profile'),
    path('profile/request-otp/', request_otp, name='request-otp'),
    path('forgot-password/', forgot_password, name='forgot-password'),
    path('verify-otp/', verify_otp_password, name='verify_otp_password'),
    path('set-new-password/', set_new_password, name='set_new_password'),
    path('user/dashboard/', dashboard_redirect, name='dashboard'),
    path("become-instructor/", BecomeInstructorView.as_view(), name="become-instructor"),
    path("payment-success/", InstructorPaymentSuccessView.as_view(), name="payment-success"),
    path('dashboard/', LearnerDashboardView.as_view(), name='learner-dashboard'),
    path("dashboard/", InstructorDashboardView.as_view(), name="instructor-dashboard"),
    path('admin-dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('verify-otp/', verify_otp, name='verify_otp'),

]
