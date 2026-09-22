from django.urls import path
from .views import *

urlpatterns = [
    path('instructor/dashboard', instructor_dashboard, name='instructor_dashboard'),

    path('instructor/assignment_create', assignment_create, name='assignment_create'),
        # path('assignment_list/<int:course_id>', assignment_list, name='assignment_list'),
        # path('courses/<int:course_id>/assignments/<int:assignment_id>/', assignment_detail, name='assignment_detail'),
        path('assignment_edit/<int:assignment_id>', assignment_edit, name='assignment_edit'),
        path('assignment_delete/<int:assignment_id>', assignment_delete, name='assignment_delete'),
        path('instructor/course_create', course_create, name='course_create'),
        path('instructor/course_edit/<int:course_id>', course_edit, name='course_edit'),
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
        path('instructor/analytics', instructor_analytics, name='instructor_analytics'),
]