from django.urls import path
from .views import *
urlpatterns = [
    path('', home, name='home'),
    path('courses/', course_list, name='course_list'),
    # path('courses/<int:course_id>/enroll/', enroll_course, name='enroll_course'),
    # path('courses/<int:course_id>/content/', course_content, name='course_content'),

    path('assignment_create', assignment_create, name='assignment_create'),
    path('assignment_list/<int:course_id>', assignment_list, name='assignment_list'),
    path('courses/<int:course_id>/assignments/<int:assignment_id>/', assignment_detail, name='assignment_detail'),
    path('assignment_edit/<int:assignment_id>', assignment_edit, name='assignment_edit'),
    path('assignment_delete/<int:assignment_id>', assignment_delete, name='assignment_delete'),

    # path('discussions_list', discussion_list, name='discussion_list'),
    # path('discussions_detail', discussion_detail, name='discussion_detail'),

    path('signup/', signup, name='signup'),
    path('signin/', signin, name='signin'),
    path('signout', signout, name='signout'),

    path('student_dashboard', student_dashboard, name='student_dashboard'),
    path('instructor_dashboard', instructor_dashboard, name='instructor_dashboard'),
    path('sponsor_dashboard', sponsor_dashboard, name='sponsor_dashboard'),
    path('fund_student', fund_student, name='fund_student'),
    path('fund_student_detail/<int:student_id>', fund_student_detail, name='fund_student_detail'),
    path('fund_course_action/<int:student_id>', fund_student_action, name='fund_course_action'),
    # path('fund_course_page', fund_course_page, name='fund_course_page'),
    path('fund-course/', fund_course_page, name='fund_course_page'),
    path('fund-course/checkout/<int:course_id>/', fund_course_checkout, name='fund_course_checkout'),
    path('fund_course_payment_process/<int:course_id>', fund_course_payment_process, name='fund_course_payment_process'),
    path('fund_course_esewa_success/<int:order_id>', fund_course_esewa_success, name='fund_course_esewa_success'),
    path('fund_course_esewa_fail/<int:order_id>', fund_course_esewa_fail, name='fund_course_esewa_fail'),

    path('course_create', course_create, name='course_create'),
    path('course_edit/<int:course_id>', course_edit, name='course_edit'),
    path('courses/<int:course_id>/', course_detail, name='course_detail'),
    path('course_delete/<int:course_id>', course_delete, name='course_delete'),
    path('course_content/<int:course_id>', course_content, name='course_content'),

    path('lesson_detail/<int:lesson_id>', lesson_detail, name='lesson_detail'),
    path('course_learn/<int:course_id>', course_learn, name='course_learn'),
    path('course_learn/<int:course_id>/<int:lesson_id>', course_learn, name='course_learn_with_lesson'),
    path('mark_lesson_completed/<int:lesson_id>', mark_lesson_completed, name='mark_lesson_completed'),
    path('create_lesson/<int:course_id>', create_lesson, name='create_lesson'),
    path('create_module/<int:course_id>', create_module, name='create_module'),

    path('checkout/<int:course_id>', checkout, name='checkout'),
    path('payment/process', process_payment, name='process_payment'),
    path('payment_history', payment_history, name='payment_history'),
    path('payment/success/', payment_success, name='payment_success'),
    path('payment/fail/', payment_fail, name='payment_fail'),
    # path('download_invoice/<int:payment_id>/', download_invoice, name='download_invoice'),
    # path('export_payments_csv/', export_payments_csv, name='export_payments_csv'),
    # path('export_payments_pdf/', export_payments_pdf, name='export_payments_pdf'),
    path('some_error_page', some_error_page, name='some_error_page'),

    path('enrolled_course', enrolled_course, name='enrolled_course'),
    path('student_profile', student_profile, name='student_profile'),
    path('update_student_profile', update_student_profile, name='update_student_profile'),
    path('change_student_password', change_student_password, name='change_student_passowrd'),
    path('completed_courses', completed_courses, name='completed_courses'),
    path('pending_assignments', pending_assignments, name='pending_assignments'),

    path('instructor_profile', instructor_profile, name='instructor_profile'),
    path('update_instructor_profile', update_instructor_profile, name='update_instructor_profile'),
    path('change_instructor_password', change_instructor_password, name='change_instructor_profile'),
    path('about', about, name='about'),
    path('view_assignment/<int:assignment_id>', view_assignment, name='view_assignment'),

#     path('assignment/<int:assignment_id>/submissions/', instructor_submissions_list, name='instructor_submissions_list'),
#    # path('submission/<int:submission_id>/view/', instructor_view_submission, name='instructor_view_submission'),

#     path('view_submitted_answer/<int:submitted_id>', instructor_view_submissions, name='view_submitted_answer'),
    path('instructor/submissions/', instructor_submissions_list, name='instructor_submitted_answers'),
    path('instructor/submission/<int:submission_id>/', instructor_submission_detail, name='instructor_submission_detail'),

    path('sponsor_profile', sponsor_profile, name='sponsor_profile'),
    path('update_sponsor_profile', update_sponosr_profile, name='update_sponsor_profile'),
    path('sponsor_checkout/<int:student_id>/', sponsor_checkout, name='sponsor_checkout'),
    path('sponsor_payment_process/<int:student_id>/', sponsor_payment_process, name='sponsor_payment_process'),
    path('sponsor_payment/success/', sponsor_payment_success, name='sponsor_payment_success'),
    path('sponsor_payment_fail/', sponsor_payment_fail, name='sponsor_payment_fail'),

    path("student_profile_view/<student_id>", student_profile_view, name="student_profile_view"),
    path('funding-history', funding_history, name='funding_history'),
]