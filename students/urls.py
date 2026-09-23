from django.urls import path
from .views import *

urlpatterns = [
        path('student/dashboard', student_dashboard, name='student_dashboard'),

        path('student/courses/', course_list, name='course_list'),
            path('student/courses/<int:course_id>/', course_detail, name='course_detail'),
            path('student/enrolled_course', enrolled_course, name='enrolled_course'),
            path('student/course_learn/<int:course_id>', course_learn, name='course_learn'),
            path('student/lesson_detail/<int:lesson_id>', lesson_detail, name='lesson_detail'),
            path('student/complete/course/<int:course_id>', complete_course, name='complete_course'),
            path('student/mark_lesson_completed/<int:lesson_id>', mark_lesson_completed, name='mark_lesson_completed'),
        
            path('student/checkout/<int:course_id>', checkout, name='checkout'),
            path('student/payment/process', process_payment, name='process_payment'),
            path('student/payment/success/', payment_success, name='payment_success'),
            path('student/payment/fail/', payment_fail, name='payment_fail'),
            path('student/payment_history', payment_history, name='payment_history'),
            path('student/some_error_page', some_error_page, name='some_error_page'),
        
            path('student/student_profile', student_profile, name='student_profile'),
            path('student/update_student_profile', update_student_profile, name='update_student_profile'),
            path('student/change_student_password', change_student_password, name='change_student_passowrd'),
            path('student/completed_courses', completed_courses, name='completed_courses'),
            path('student/pending_assignments', pending_assignments, name='pending_assignments'),
]