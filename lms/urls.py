from django.urls import path
from .views import *
urlpatterns = [
    path('', home, name='home'),
    path('about', about, name='about'),

    path('sponsor/dashboard', sponsor_dashboard, name='sponsor_dashboard'),

    path('sponsor/fund-student', fund_student, name='fund_student'),
    path('fund_student_detail/<int:student_id>', fund_student_detail, name='fund_student_detail'),
    path('fund_course_action/<int:student_id>', fund_student_action, name='fund_course_action'),
    path('sponsor/fund-course/', fund_course_page, name='fund_course_page'),
    path('fund-course/checkout/<int:course_id>/', fund_course_checkout, name='fund_course_checkout'),
    path('fund_course_payment_process/<int:course_id>', fund_course_payment_process, name='fund_course_payment_process'),
    path('fund_course_esewa_success/<int:order_id>', fund_course_esewa_success, name='fund_course_esewa_success'),
    path('fund_course_esewa_fail/<int:order_id>', fund_course_esewa_fail, name='fund_course_esewa_fail'),

    path('sponsor/sponsor_profile', sponsor_profile, name='sponsor_profile'),
    path('sponsor/update_sponsor_profile', update_sponsor_profile, name='update_sponsor_profile'),
    path('sponsor/sponsor_checkout/<int:student_id>/', sponsor_checkout, name='sponsor_checkout'),
    path('sponsor/sponsor_payment_process/<int:student_id>/', sponsor_payment_process, name='sponsor_payment_process'),
    path('sponsor/payment/success/', sponsor_payment_success, name='sponsor_payment_success'),
    path('sponsor/payment/fail/', sponsor_payment_fail, name='sponsor_payment_fail'),

    path("sponsor/student/profile_view/<student_id>", student_profile_view, name="student_profile_view"),
    path('sponsor/course/profile_view/<int:course_id>', course_profile_view, name='course_profile_view'),
    path('sponsor/funding-history', funding_history, name='funding_history'),

    path('admin/admin-dashboard', admin_dashboard, name='admin_dashboard'),
    path('admin/export-report', export_report_pdf, name='export_report_pdf'),
]