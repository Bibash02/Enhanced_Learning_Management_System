from django.urls import path
from .views import *
urlpatterns = [
    path('', home, name='home'),
    path('student/courses/', course_list, name='course_list'),
    path('signup/', signup, name='signup'),
    path('signin/', signin, name='signin'),
    path('signout', signout, name='signout'),
    path('about', about, name='about'),

    path('student/dashboard', student_dashboard, name='student_dashboard'),
    path('instructor/dashboard', instructor_dashboard, name='instructor_dashboard'),
    path('sponsor/dashboard', sponsor_dashboard, name='sponsor_dashboard'),

    path('instructor/assignment_create', assignment_create, name='assignment_create'),
    # path('assignment_list/<int:course_id>', assignment_list, name='assignment_list'),
    # path('courses/<int:course_id>/assignments/<int:assignment_id>/', assignment_detail, name='assignment_detail'),
    path('assignment_edit/<int:assignment_id>', assignment_edit, name='assignment_edit'),
    path('assignment_delete/<int:assignment_id>', assignment_delete, name='assignment_delete'),
    path('instructor/course_create', course_create, name='course_create'),
    path('instructor/course_edit/<int:course_id>', course_edit, name='course_edit'),
    path('student/courses/<int:course_id>/', course_detail, name='course_detail'),
    path('course_delete/<int:course_id>', course_delete, name='course_delete'),
    path('course_content/<int:course_id>', course_content, name='course_content'),
    path('instructor/create_lesson/<int:course_id>', create_lesson, name='create_lesson'),
    path('instructor/create_module/<int:course_id>', create_module, name='create_module'),

    path('instructor/instructor_profile', instructor_profile, name='instructor_profile'),
    path('instructor/update_instructor_profile', update_instructor_profile, name='update_instructor_profile'),
    path('instructor/change_instructor_password', change_instructor_password, name='change_instructor_profile'),
    path('student/view_assignment/<int:assignment_id>', view_assignment, name='view_assignment'),

    path('instructor/submissions/', instructor_submissions_list, name='instructor_submitted_answers'),
    path('instructor/submission/<int:submission_id>/', instructor_submission_detail, name='instructor_submission_detail'),

    path('student/lesson_detail/<int:lesson_id>', lesson_detail, name='lesson_detail'),
    path('student/course_learn/<int:course_id>', course_learn, name='course_learn'),
    path('student/mark_lesson_completed/<int:lesson_id>', mark_lesson_completed, name='mark_lesson_completed'),

    path('student/checkout/<int:course_id>', checkout, name='checkout'),
    path('student/payment/process', process_payment, name='process_payment'),
    path('student/payment_history', payment_history, name='payment_history'),
    path('student/payment/success/', payment_success, name='payment_success'),
    path('student/payment/fail/', payment_fail, name='payment_fail'),
    path('student/some_error_page', some_error_page, name='some_error_page'),

    path('student/enrolled_course', enrolled_course, name='enrolled_course'),
    path('student/student_profile', student_profile, name='student_profile'),
    path('student/update_student_profile', update_student_profile, name='update_student_profile'),
    path('student/change_student_password', change_student_password, name='change_student_passowrd'),
    path('student/completed_courses', completed_courses, name='completed_courses'),
    path('student/pending_assignments', pending_assignments, name='pending_assignments'),

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
    path('sponsor/sponsor_payment/success/', sponsor_payment_success, name='sponsor_payment_success'),
    path('sponsor/sponsor_payment/fail/', sponsor_payment_fail, name='sponsor_payment_fail'),

    path("sponsor/student_profile_view/<student_id>", student_profile_view, name="student_profile_view"),
    path('sponsor/funding-history', funding_history, name='funding_history'),

    path('admin/admin-dashboard', admin_dashboard, name='admin_dashboard'),
]