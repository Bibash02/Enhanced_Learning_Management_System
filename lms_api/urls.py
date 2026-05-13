from django.urls import path
from .views import *

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('login/', LoginAPIView.as_view(), name='login'),

    path('instructor/courses/list/', InstructorCoursesAPIView.as_view(), name='my-courses'),
    path('instructor/courses/list/<int:course_id>/edit/', CourseUpdateAPIView.as_view(), name='edit-course'),
    path('instructor/courses/create/', CourseCreateAPIView.as_view(), name='create-course'),
    path('instructor/courses/<int:course_id>/assignments/create/', AssignmentCreateAPIView.as_view(), name='create-assignment'),
    path('instructor/assignments/<int:assignment_id>/submissions/', AssignmentSubmissionsAPIView.as_view(), name='assignment-submissions'),
    path('instructor/submissions/<int:submission_id>/grade/', GradeSubmissionAPIView.as_view(), name='grade-submission'),
    
    path('student/courses/', StudentCourseListAPIView.as_view(), name='student_course_list'),

    # path('student/courses/<int:course_id>/checkout/', CheckoutAPIView.as_view(), name='checkout'),
    # path('student/payment/esewa/success', EsewaSuccessAPIView.as_view(), name='payment_success_api'),
    # path('student/payment/esewa/fail', EsewaFailAPIView.as_view(), name='payment_fail_api'),
    path('student/courses/<int:course_id>/', StudentCourseDetailAPIView.as_view(), name='student_course_detail'),
    path('student/courses/enroll/<int:course_id>/', EnrollCourseAPIView.as_view(), name='enroll-course'),
    path('student/courses/enrolled/', StudentEnrolledCoursesAPIView.as_view(), name='student_enrolled_courses'),
    path('student/courses/<int:course_id>/assignments/', CourseAssignmentsAPIView.as_view(), name='course-assignments'),
    path('student/courses/<int:course_id>/assignments/<int:assignment_id>/submit/', SubmitAssignmentAPIView.as_view(), name='submit-assignment'),

    path('sponsor/students/', SponsorStudentListAPIView.as_view(), name='sponsor-student-list'),
    path('sponsor/fund/student/', FundStudentAPIView.as_view(), name='fund-student'),
    path('sponsor/funded/students/', SponsoredStudentsListAPIView.as_view(), name='sponsored-students-list'),
    path('sponsor/courses/', CourseListForFundingAPIView.as_view(), name='course-list-for-funding'),
    path('sponsor/fund/course/', FundCourseAPIView.as_view(), name='fund-course'),
    path('sponsor/funded/courses/', SponsoredCoursesListAPIView.as_view(), name='sponsored-courses-list'),
    path('sponsor/fund/history/', FundingHistoryAPIView.as_view(), name='funding-history'),
]