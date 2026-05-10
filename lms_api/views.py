from decimal import Decimal
from django.urls import reverse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from lms.utils import generate_signature
from lms.views import apply_funding
from .permissions import IsStudent, IsInstructor, IsSponsor
from django.shortcuts import get_object_or_404
from rest_framework.filters import SearchFilter
from rest_framework.generics import ListAPIView
from .email_service import send_enrollment_email
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.pagination import PageNumberPagination
import uuid
import base64
import json
from django.contrib.auth.models import User
from .serializers import *
from .models import *

class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            # SEND EMAIL AFTER SUCCESS
            send_mail(
                subject="Welcome to Our LMS Platform",
                message=f"""
                    Hello {user.get_full_name() or user.username},

                    Your account has been successfully created.

                    You can now login and start learning courses.

                    Thank you for joining us!

                    Best regards,
                    LMS Team
                """,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

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
                    "role": user.profile.role
                })

            return Response({"error": "Invalid email or password"}, status=400)

        return Response(serializer.errors, status=400)

class CoursePagination(PageNumberPagination):
    page_size = 2
    page_size_query_param = 'page_size'
    max_page_size = 10
    
# View all published courses
class StudentCourseListAPIView(ListAPIView):
    serializer_class = CourseSerializer
    permission_classes = [IsStudent]
    filter_backends = [SearchFilter]
    search_fields = ['title', 'level', 'instructor__username',]
    pagination_class = CoursePagination

    def get_queryset(self):
        return Course.objects.filter(is_published=True)

# View single course details
class StudentCourseDetailAPIView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, is_published=True)
        serializer = CourseSerializer(course)
        return Response(serializer.data, status=status.HTTP_200_OK)

class CheckoutAPIView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, course_id):

        user = request.user

        course = get_object_or_404(
            Course,
            id=course_id,
            is_published=True
        )

        # already enrolled
        if Enrollment.objects.filter(
            student=user,
            course=course
        ).exists():
            return Response(
                {"detail": "You are already enrolled in this course."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # already purchased
        if Order.objects.filter(
            user=user,
            course=course,
            status="Completed"
        ).exists():
            return Response(
                {"detail": "You already purchased this course."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # VALIDATE INPUTS
        payment_type = request.data.get("payment_type", "").strip()

        if not payment_type:
            return Response(
                {"detail": "Payment type is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if payment_type not in ["esewa", "cod"]:
            return Response(
                {"detail": "Invalid payment type."},
                status=status.HTTP_400_BAD_REQUEST
            )

        full_name = request.data.get("name", "").strip()
        email = request.data.get("email", "").strip()
        phone = request.data.get("phone", "").strip()
        address = request.data.get("address", "").strip()
        city = request.data.get("city", "").strip()

        if not full_name:
            return Response(
                {"detail": "Full name is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not phone:
            return Response(
                {"detail": "Phone number is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not address:
            return Response(
                {"detail": "Address is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not city:
            return Response(
                {"detail": "City is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # SPONSORSHIP LOGIC
        transaction_uuid = str(uuid.uuid4())

        fundings = Funding.objects.filter(
            course=course,
            status="Completed"
        )

        available_funding = sum(
            (f.amount - f.used_amount)
            for f in fundings
        )

        course_price = Decimal(str(course.price))

        sponsor_used = min(course_price, available_funding)

        final_price = course_price - sponsor_used

        if final_price < 0:
            final_price = Decimal("0.00")

        # FULLY SPONSORED COURSE
        if final_price == 0:

            order = Order.objects.create(
                user=user,
                course=course,
                full_name=full_name,
                email=email,
                phone=phone,
                address=address,
                city=city,
                country="Nepal",
                amount=0,
                sponsor_used=sponsor_used,
                payment_type="cod",
                transaction_uuid=transaction_uuid,
                status="Sponsored"
            )

            # apply funding
            apply_funding(course, sponsor_used)

            Enrollment.objects.get_or_create(
                student=user,
                course=course
            )

            return Response(
                {
                    "message": "Course fully sponsored.",
                    "enrolled": True,
                    "course_id": course.id
                },
                status=status.HTTP_200_OK
            )

        # CREATE ORDER
        order = Order.objects.create(
            user=user,
            course=course,
            full_name=full_name,
            email=email,
            phone=phone,
            address=address,
            city=city,
            country="Nepal",
            amount=final_price,
            sponsor_used=sponsor_used,
            payment_type=payment_type,
            transaction_uuid=transaction_uuid,
            status="Pending"
        )

        # CASH ON DELIVERY
        if payment_type == "cod":

            order.status = "Completed"
            order.save()

            # apply sponsor funding
            if sponsor_used > 0:
                apply_funding(course, sponsor_used)

            Enrollment.objects.get_or_create(
                student=user,
                course=course
            )

            return Response(
                {
                    "message": "Order placed successfully.",
                    "enrolled": True,
                    "course_id": course.id
                },
                status=status.HTTP_200_OK
            )

        # ESEWA PAYMENT
        if payment_type == "esewa":

            product_code = settings.ESEWA_PRODUCT_CODE
            secret_key = settings.ESEWA_SECRET_KEY

            total_amount = format(final_price, ".2f")

            signature = generate_signature(
                total_amount,
                transaction_uuid,
                product_code,
                secret_key
            )

            success_url = request.build_absolute_uri(
                reverse("payment_success_api")
            )

            failure_url = request.build_absolute_uri(
                reverse("payment_fail_api")
            )

            return Response(
                {
                    "payment_url": "https://rc-epay.esewa.com.np/api/epay/main/v2/form",
                    "payment_data": {
                    "amount": total_amount,
                    "tax_amount": "0",
                    "total_amount": total_amount,
                    "transaction_uuid": transaction_uuid,
                    "product_code": product_code,
                    "product_service_charge": "0",
                    "product_delivery_charge": "0",
                    "success_url": success_url,
                    "failure_url": failure_url,
                    "signed_field_names": "total_amount,transaction_uuid,product_code",
                    "signature": signature
                }
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {"detail": "Invalid request."},
            status=status.HTTP_400_BAD_REQUEST
        )

class EsewaSuccessAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        encoded_data = request.GET.get("data")

        if not encoded_data:
            return Response({
                "detail": "Missing payment data."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            decoded_data = base64.b64decode(encoded_data).decode("utf-8")
            payment_data = json.loads(decoded_data)

            transaction_uuid = payment_data.get("transaction_uuid")
            payment_status = payment_data.get("status")

            order = get_object_or_404(Order, transaction_uuid = transaction_uuid)

            if payment_status == "COMPLETE":
                order.status = "Completed"
                order.save()

                Enrollment.objects.get_or_create(student = request.user, course = order.course)

                return Response({
                    "message": "Payment Successful."
                })
            order.status = "Failed"
            order.save()

            return Response({
                "message": "Payment Failed."
            })
        except Exception as e:
            return Response({
                "detail": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
class EsewaFailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        transaction_uuid = request.GET.get("transaction_uuid")
        
        if transaction_uuid:
            order = Order.objects.filter(transaction_uuid = transaction_uuid).first()

            if order:
                order.status = "Failed"
                order.save()

        return Response({
            "message": "Payment Failed."
        })

# Enroll in a course
class EnrollCourseAPIView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, is_published=True)
        serializer = CourseSerializer(course)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, is_published=True)
        enrollment, created = Enrollment.objects.get_or_create(student=request.user, course=course)
        if not created:
            return Response({"detail": "Already enrolled."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Send email to instructor
        instructor = course.instructor
        student = request.user

        # email to instructor
        send_mail(
            subject=f"New Student Enrolled: {course.title}",
            message=f"""
                Hello {instructor.get_full_name() or instructor.username},

                A new student has enrolled in your course.

                Course: {course.title}
                Student: {student.get_full_name() or student.username}

                Regards,
                LMS System
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instructor.email],
            fail_silently=False,
        )

        # email to student
        send_mail(
            subject="Enrollment Successful 🎓",
            message=f"""
                Hello {student.get_full_name() or student.username},

                You have successfully enrolled in:

                Course: {course.title}

                You can now start learning from your dashboard.

                Good luck!
                LMS Team
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[student.email],
            fail_silently=False,
        )

        serializer = EnrollmentSerializer(enrollment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

# View all enrolled courses by student
class StudentEnrolledCoursesAPIView(APIView):
    permission_classes = [IsStudent]
    pagination_class = CoursePagination

    def get(self, request):
        enrollment = Enrollment.objects.filter(student=request.user)
        serializer = EnrollmentSerializer(enrollment, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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

    def get(self, request, *args, **kwargs):
        assignment_id = kwargs.get('assignment_id')
        assignment = get_object_or_404(Assignment, id=assignment_id)

        serializer = AssignmentSerializer(assignment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        assignment_id = kwargs.get('assignment_id')
        assignment = get_object_or_404(Assignment, id=assignment_id)

        # STRONG duplicate prevention
        if Submission.objects.filter(
            assignment=assignment,
            student=request.user
        ).exists():
            return Response(
                {"detail": "You have already submitted this assignment."},
                status=status.HTTP_400_BAD_REQUEST
            )

        content = request.data.get('content', '').strip()
        answers = request.data.get('answers', [])

        # fix JSON string issue
        if isinstance(answers, str):
            try:
                answers = json.loads(answers)
            except:
                answers = []

        # block empty submission
        has_valid_answer = any(
            (ans.get('answer_text') and ans.get('answer_text').strip()) or ans.get('answer_file')
            for ans in answers
        )

        if not content and not has_valid_answer:
            return Response(
                {"detail": "Submission cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # create submission
        submission = Submission.objects.create(
            assignment=assignment,
            student=request.user,
            content=content
        )

        # save answers (TEXT + FILE supported)
        for ans in answers:
            question_id = ans.get('question_id')
            answer_text = (ans.get('answer_text') or '').strip()

            # file must come from request.FILES (FormData)
            answer_file_key = ans.get('answer_file_key')
            answer_file = request.FILES.get(answer_file_key) if answer_file_key else None

            # skip invalid rows
            if not question_id:
                continue

            # allow text OR file
            if not answer_text and not answer_file:
                continue

            StudentAnswer.objects.create(
                submission=submission,
                question_id=question_id,
                answer_text=answer_text if answer_text else None,
                answer_file=answer_file
            )

            # email to instructor
            instructor = assignment.course.instructor

        send_mail(
            subject=f"New Assignment Submission: {assignment.title}",
            message=f"""
                Hello {instructor.get_full_name() or instructor.username},

                A student has submitted an assignment.

                Assignment: {assignment.title}
                Student: {request.user.get_full_name() or request.user.username}

                Please review it from your dashboard.

                Regards,
                LMS System
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instructor.email],
            fail_silently=False,
        )

        return Response(
            {
                "message": "Assignment submitted successfully",
                "submission_id": submission.id
            },
            status=status.HTTP_201_CREATED
        )

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
class InstructorCoursesAPIView(ListAPIView):
    permission_classes = [IsInstructor]
    serializer_class = CourseSerializer
    filter_backends = [SearchFilter]
    search_fields = ['title',]
    pagination_class = CoursePagination

    def get_queryset(self):
        return Course.objects.filter(instructor=self.request.user)
    
# Update specific course
class CourseUpdateAPIView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, instructor=request.user)
        serializer = CourseSerializer(course)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, instructor = request.user)
        serializer = CourseSerializer(course, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, instructor=request.user)
        course.delete()
        return Response({"detail": "Course deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

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

            # Get all enrolled students
            enrolled_students = Enrollment.objects.filter(course=course)

            # Send email notification to each student
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
    pagination_class = CoursePagination

    def get(self, request, assignment_id):
        assignment = get_object_or_404(Assignment, id=assignment_id, created_by=request.user)
        submissions = Submission.objects.filter(assignment=assignment)
        serializer = SubmissionSerializer(submissions, many=True)
        return Response(serializer.data)

class GradeSubmissionAPIView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request, submission_id):
        submission = get_object_or_404(Submission, id=submission_id)
        serializer = SubmissionSerializer(submission)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, submission_id):
        submission = get_object_or_404(
            Submission,
            id=submission_id,
            assignment__created_by=request.user
        )

        grade = request.data.get('grade')
        feedback = request.data.get('feedback', '').strip()

        # BLOCK EMPTY GRADE
        if grade is None or str(grade).strip() == "":
            return Response(
                {"detail": "Grade cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # optional: validate grade is number
        try:
            grade = int(grade)
        except ValueError:
            return Response(
                {"detail": "Grade must be a number."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # optional: validate range (0–100)
        if grade < 0 or grade > 100:
            return Response(
                {"detail": "Grade must be between 0 and 100."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # save grade
        submission.grade = grade
        submission.feedback = feedback
        submission.status = 'graded'
        submission.save()

        # email logic (unchanged)
        student_user = submission.student
        student_email = getattr(student_user, 'email', None)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER)

        email_sent = False

        if student_email and from_email:
            subject = f"Your Assignment '{submission.assignment.title}' has been Graded!"
            message = (
                f"Hello {student_user.first_name or student_user.username},\n\n"
                f"Your submission has been graded.\n"
                f"Grade: {grade}\n"
                f"Feedback: {feedback}\n\n"
                "Best regards,\nLMS Team"
            )
            try:
                send_mail(subject, message, from_email, [student_email], fail_silently=False)
                email_sent = True
            except Exception as e:
                print("Email sending error:", e)

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
    pagination_class = CoursePagination

    def get_queryset(self):
        return UserProfile.objects.filter(role='student').select_related('user')  
    
# Fund a student
class FundStudentAPIView(APIView):
    permission_classes = [IsSponsor]

    def get(self, request):
        serializer = FundStudentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
    pagination_class = CoursePagination

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
    pagination_class = CoursePagination

    def get(self, request):
        courses = Course.objects.all()  
        paginator = PageNumberPagination()
        paginator.page_size = 5
        serializer = CourseSerializer(courses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# Fund a course
class FundCourseAPIView(APIView):
    permission_classes = [IsSponsor]

    def get(self, request):
        serializer = FundCourseSerializer(data = request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
    pagination_class = CoursePagination

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
    pagination_class = CoursePagination

    def get(self, request):
        fundings = Funding.objects.filter(sponsor=request.user).order_by('-funded_at')

        serializer = FundingHistorySerializer(fundings, many=True)
        return Response(serializer.data)