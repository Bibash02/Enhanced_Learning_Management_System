from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .permissions import IsStudent, IsInstructor, IsSponsor
from django.shortcuts import get_object_or_404
from rest_framework.filters import SearchFilter
from rest_framework.generics import ListAPIView
from .email_service import send_enrollment_email
from django.core.mail import send_mail
from django.conf import settings

from django.contrib.auth.models import User
from .serializers import *
from .models import *

class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            return Response({
                "message": "Account created successfully!",
                "email": user.email,
                "role": user.userprofile.role
            }, status=201)

        return Response(serializer.errors, status=400)
    
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            email = serializer.validated_data.get("email")
            password = serializer.validated_data.get("password")

            # Check if email exists
            try:
                user_obj = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({"error": "Invalid email or password"}, status=400)

            # Authenticate
            user = authenticate(username=user_obj.username, password=password)

            if user:
                token, _ = Token.objects.get_or_create(user=user)
                return Response({
                    "token": token.key,
                    "username": user.first_name,
                    "role": user.userprofile.role
                })

            return Response({"error": "Invalid email or password"}, status=400)

        return Response(serializer.errors, status=400)

# List all enrolled courses
class StudentCoursesAPIView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        enrollments = Enrollment.objects.filter(student=request.user)
        serializer = EnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data)
    
# View all published courses
class StudentCourseListAPIView(ListAPIView):
    serializer_class = CourseSerializer
    permission_classes = [IsStudent]
    filter_backends = [SearchFilter]
    search_fields = ['title', 'level', 'instructor__username',]

    def get_queryset(self):
        return Course.objects.filter(is_published=True)

# View single course details
class StudentCourseDetailAPIView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, is_published=True)
        serializer = CourseSerializer(course)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
# Enroll in a course
class EnrollCourseAPIView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, is_published=True)
        enrollment, created = Enrollment.objects.get_or_create(student=request.user, course=course)
        if not created:
            return Response({"detail": "Already enrolled."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Send email to instructor
        instructor = course.instructor     # assuming Course model has instructor FK
        send_enrollment_email(
            student=request.user,
            instructor=instructor,
            course=course
        )
        serializer = EnrollmentSerializer(enrollment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

# View assignments of a course
class CourseAssignmentsAPIView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, course_id):
        # Check student enrolled
        is_enrolled = Enrollment.objects.filter(
            student=request.user,
            course_id=course_id
        ).exists()

        if not is_enrolled:
            return Response(
                {"detail": "You are not enrolled in this course."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        assignments = Assignment.objects.filter(course_id=course_id)
        serializer = AssignmentSerializer(assignments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# Submit assignment
class SubmitAssignmentAPIView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, assignment_id):
        assignment = get_object_or_404(Assignment, id=assignment_id)
        content = request.data.get('content', '')

        # Create submission
        submission, created = Submission.objects.get_or_create(
            assignment=assignment,
            student=request.user,
            defaults={'content': content}
        )
        if not created:
            return Response({"detail": "Assignment already submitted."}, status=status.HTTP_400_BAD_REQUEST)

        # Save answers if any
        answers = request.data.get('answers', [])
        for ans in answers:
            StudentAnswer.objects.create(
                submission=submission,
                question_id=ans['question_id'],
                answer_text=ans['answer_text']
            )

        serializer = SubmissionSerializer(submission)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

# View grades
class MyGradesAPIView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        submissions = Submission.objects.filter(student=request.user)
        serializer = SubmissionSerializer(submissions, many=True)
        return Response(serializer.data)

# Create a course
class CourseCreateAPIView(APIView):
    permission_classes = [IsInstructor]

    def post(self, request):
        serializer = CourseSerializer(data=request.data)
        if serializer.is_valid():
            course = serializer.save(instructor=request.user)
            return Response(CourseSerializer(course).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# List instructor courses
class InstructorCoursesAPIView(APIView):
    permission_classes = [IsInstructor]
    serializer_class = CourseSerializer
    filter_backends = [SearchFilter]
    search_fields = ['title',]

    def get_queryset(self):
        return Course.objects.filter(instructor=self.request.user)

# Create assignment for course
class AssignmentCreateAPIView(APIView):
    permission_classes = [IsInstructor]

    def post(self, request, course_id):
        # Check if instructor owns this course
        course = get_object_or_404(Course, id=course_id, instructor=request.user)

        serializer = AssignmentSerializer(data=request.data)
        
        if serializer.is_valid():
            # Save assignment with course
            assignment = serializer.save(course=course)

            # 🔹 Get all enrolled students
            enrolled_students = Enrollment.objects.filter(course=course)

            # 🔹 Send email notification to each student
            subject = f"New Assignment Added: {assignment.title}"
            message = (
                f"Hello Student,\n\n"
                f"A new assignment has been added in your course: {course.title}.\n\n"
                f"Assignment Title: {assignment.title}\n"
                f"Description: {assignment.description}\n"
                f"Deadline: {assignment.deadline}\n\n"
                f"Please log in to your LMS portal and complete it on time.\n\n"
                f"Best regards,\n"
                f"LMS Team"
            )

            for enroll in enrolled_students:
                student_user = enroll.student.user

                try:
                    send_mail(
                        subject,
                        message,
                        settings.EMAIL_HOST_USER,
                        [student_user.email],
                        fail_silently=True
                    )
                except Exception as e:
                    print("Email Error:", e)

            return Response(
                {"message": "Assignment created and students notified!", "data": serializer.data},
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# View submissions for an assignment
class AssignmentSubmissionsAPIView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request, assignment_id):
        assignment = get_object_or_404(Assignment, id=assignment_id, created_by=request.user)
        submissions = Submission.objects.filter(assignment=assignment)
        serializer = SubmissionSerializer(submissions, many=True)
        return Response(serializer.data)

# Grade a submission
class GradeSubmissionAPIView(APIView):
    permission_classes = [IsInstructor]

    def post(self, request, submission_id):
        submission = get_object_or_404(
            Submission,
            id=submission_id,
            assignment__created_by=request.user
        )
        grade = request.data.get('grade')
        feedback = request.data.get('feedback', '')

        submission.grade = grade
        submission.feedback = feedback
        submission.status = 'graded'
        submission.save()

        # Send email to the student
        student_user = submission.student  # assuming submission.student is a User instance
        student_email = getattr(student_user, 'email', None)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER)

        if student_email and from_email:
            subject = f"Your Assignment '{submission.assignment.title}' has been Graded!"
            message = (
                f"Hello {student_user.first_name or student_user.username},\n\n"
                f"Your submission for the assignment '{submission.assignment.title}' has been graded.\n"
                f"Grade: {grade}\n"
                f"Feedback: {feedback}\n\n"
                "Best regards,\n"
                "LMS Team"
            )
            try:
                send_mail(subject, message, from_email, [student_email], fail_silently=False)
                email_sent = True
            except Exception as e:
                print("Email sending error:", e)
                email_sent = False
        else:
            email_sent = False

        return Response(
            {
                "submission": SubmissionSerializer(submission).data,
                "email_sent": email_sent
            },
            status=status.HTTP_200_OK
        )

class SponsorStudentListAPIView(ListAPIView):
    permission_classes = [IsSponsor]
    serializer_class = StudentListSerializer
    filter_backends = [SearchFilter]
    search_fields = ['user__username', 'user__email',]

    def get_queryset(self):
        return UserProfile.objects.filter(role='student').select_related('user')  # adjust if your user model has "role"
    
# Fund a student
class FundStudentAPIView(APIView):
    permission_classes = [IsSponsor]

    def post(self, request):
        serializer = FundStudentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        student_id = serializer.validated_data['student_id']
        amount = serializer.validated_data['amount']

        #  Get the UserProfile (student) object — Funding.student expects a UserProfile
        student_profile = get_object_or_404(UserProfile, id=student_id, role='student')

        #  Get the related Django User object
        student_user = student_profile.user

        #  Create the funding record
        funding = Funding.objects.create(
            sponsor=request.user,
            student=student_profile,
            amount=amount,
            status='Completed'
        )

        # Prepare & send the email (only if student has email)
        student_email = getattr(student_user, 'email', None)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER if hasattr(settings, 'EMAIL_HOST_USER') else None)

        subject = "You Have Received a Sponsorship!"
        message = (
            f"Hello {student_user.first_name or student_user.username},\n\n"
            f"You have received a new sponsorship from {request.user.get_full_name() or request.user.username}.\n"
            f"Funded Amount: Rs. {amount}\n\n"
            "You can now continue your learning journey!\n\n"
            "Best Regards,\n"
            "LMS Team"
        )

        if student_email and from_email:
            try:
                send_mail(
                    subject,
                    message,
                    from_email,
                    [student_email],
                    fail_silently=False,
                )
                email_sent = True
            except Exception as e:
                # Log the exception in real app (here we just capture it)
                print("Email sending error:", e)
                email_sent = False
        else:
            email_sent = False

        return Response(
            {
                "message": f"Funded {student_user.username} successfully!",
                "funding_id": funding.id,
                "email_sent": email_sent
            },
            status=status.HTTP_201_CREATED
        )

# List all students funded by sponsor
class SponsoredStudentsListAPIView(APIView):
    permission_classes = [IsSponsor]

    def get(self, request):
        sponsor = request.user
        student_fundings = Funding.objects.filter(
            sponsor=sponsor, student__isnull=False
        ).select_related('student', 'student__user')

        serializer_data = [
            {
                "funding_id": f.id,
                "student_id": f.student.id,
                "student_username": f.student.user.username,
                "student_email": f.student.user.email,
                "amount": f.amount,
                "status": f.status,
                "funded_at": f.funded_at,
            }
            for f in student_fundings
        ]

        return Response(serializer_data, status=status.HTTP_200_OK)

# List all courses available for funding
class CourseListForFundingAPIView(APIView):
    permission_classes = [IsSponsor]

    def get(self, request):
        courses = Course.objects.all()   # Fetch all created courses
        serializer = CourseSerializer(courses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# Fund a course
class FundCourseAPIView(APIView):
    permission_classes = [IsSponsor]

    def post(self, request):
        serializer = FundCourseSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        course_id = serializer.validated_data['course_id']
        amount = serializer.validated_data['amount']

        # Fetch course
        course = get_object_or_404(Course, id=course_id)

        # Get the instructor user
        instructor = course.instructor
        instructor_email = instructor.email

        # Create funding record
        funding = Funding.objects.create(
            sponsor=request.user,
            course=course,
            amount=amount,
            status='Completed'
        )

        # Email Notification to Instructor
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL',
                             settings.EMAIL_HOST_USER if hasattr(settings, 'EMAIL_HOST_USER') else None)

        subject = f"Your Course '{course.title}' Has Received Sponsorship!"
        message = (
            f"Hello {instructor.first_name or instructor.username},\n\n"
            f"Your course '{course.title}' has received a new sponsorship from "
            f"{request.user.get_full_name() or request.user.username}.\n\n"
            f"Sponsor Contribution: Rs. {amount}\n\n"
            f"Keep up the great work creating valuable content!\n\n"
            "Best Regards,\n"
            "LMS Team"
        )

        email_sent = False
        if instructor_email and from_email:
            try:
                send_mail(
                    subject,
                    message,
                    from_email,
                    [instructor_email],
                    fail_silently=False
                )
                email_sent = True
            except Exception as e:
                print("Email error:", e)

        return Response(
            {
                "message": f"Funded course '{course.title}' successfully!",
                "course": course.title,
                "funding_id": funding.id,
                "email_sent": email_sent
            },
            status=status.HTTP_201_CREATED
        )

# List all courses funded by sponsor
class SponsoredCoursesListAPIView(APIView):
    permission_classes = [IsSponsor]

    def get(self, request):
        sponsor = request.user
        course_fundings = Funding.objects.filter(
            sponsor=sponsor, course__isnull=False
        ).select_related('course')

        serializer_data = [
            {
                "funding_id": f.id,
                "course_id": f.course.id,
                "course_title": f.course.title,
                "amount": f.amount,
                "status": f.status,
                "funded_at": f.funded_at,
            }
            for f in course_fundings
        ]

        return Response(serializer_data, status=status.HTTP_200_OK)

# View funding history
class FundingHistoryAPIView(APIView):
    permission_classes = [IsSponsor]

    def get(self, request):
        fundings = Funding.objects.filter(sponsor=request.user).order_by('-funded_at')
        serializer = FundingHistorySerializer(fundings, many=True)
        return Response(serializer.data)