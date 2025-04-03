from django.urls import path
from .views import register, verify_otp, login_view, logout_view, \
    UserProfileUpdateView, forgot_password, LearnerDashboardView, \
    InstructorDashboardView, InstructorPaymentSuccessView, BecomeInstructorView, AdminDashboardView, request_otp, \
    dashboard_redirect, verify_otp_password, set_new_password, users_list, instructors_list, learners_list, \
    pending_classes, class_list, approved_classes, ongoing_classes, enrollment_list, paid_enrollments, \
    booked_enrollments, order_list, revenue_view, feedback_list

app_name = 'accounts'

urlpatterns = [
    path('register/', register, name='register'),
    path('verify-otp/', verify_otp, name='verify_otp'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', UserProfileUpdateView.as_view(), name='profile'),
    path('profile/request-otp/', request_otp, name='request-otp'),
    path('forgot-password/', forgot_password, name='forgot-password'),
    path('verify-otp-password/', verify_otp_password, name='verify_otp_password'),
    path('set-new-password/', set_new_password, name='set_new_password'),
    path('user/dashboard/', dashboard_redirect, name='dashboard'),
    path("become-instructor/", BecomeInstructorView.as_view(), name="become-instructor"),
    path("payment-success/", InstructorPaymentSuccessView.as_view(), name="payment-success"),
    path('dashboard/', LearnerDashboardView.as_view(), name='learner-dashboard'),
    path("dashboard/", InstructorDashboardView.as_view(), name="instructor-dashboard"),
    path('admin-dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('users/', users_list, name='users_list'),
    path("instructors/", instructors_list, name="instructors_list"),
    path("learners/", learners_list, name="learners_list"),
    path("pending-classes/", pending_classes, name="pending_classes"),
    path("class-list/", class_list, name="class_list"),
    path("approved-classes/", approved_classes, name="approved_classes"),
    path("ongoing-classes/", ongoing_classes, name="ongoing_classes"),
    path('enrollments/', enrollment_list, name='enrollment_list'),
    path('enrollments/paid/', paid_enrollments, name='paid_enrollments'),
    path('enrollments/booked/', booked_enrollments, name='booked_enrollments'),
    path('orders/', order_list, name='order_list'),
    path('revenue/', revenue_view, name='revenue'),
    path('feedbacks/', feedback_list, name='feedback_list'),

]
