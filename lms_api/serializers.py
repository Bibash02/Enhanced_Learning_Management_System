from rest_framework import serializers
from django.contrib.auth.models import User
from lms.models import *

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name']
        read_only_fields = ['id']

class SponsorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = SponsorProfile
        fields = ['user', 'budget', 'company_name', 'website']

class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=['student', 'instructor', 'sponsor'])
    image = serializers.ImageField(required=False)

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError("Passwords do not match!")
        return data

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists!")
        return value

    def create(self, validated_data):
        username = validated_data.get("username")
        email = validated_data.get("email")
        password = validated_data.get("password")
        role = validated_data.get("role")
        image = validated_data.get("image", None)

        # Create user
        user = User.objects.create_user(
            username=username,   
            email=email,
            password=password,
            first_name=username
        )

        # Create user profile
        UserProfile.objects.create(
            user=user,
            role=role,
            image=image if image else "images/default.jpg"
        )

        if role == "sponsor":
            SponsorProfile.objects.create(
                user=user,
                budget=0,
                company_name="",
                website=None
            )

        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

class CourseSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.get_full_name', read_only=True)

    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'instructor_name', 'category', 'level', 'price', 'duration_hours', 'thumbnail', 'is_published', 'created_at']

class EnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'student', 'student_name', 'course', 'course_title', 'enrolled_at']


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'question_text', 'option1', 'option2', 'option3', 'option4', 'correct_option']

class AssignmentSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    class Meta:
        model = Assignment
        fields = ['id', 'course', 'title', 'description', 'due_date', 'created_at', 'questions']

class SubmissionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Submission
        fields = ['id', 'assignment', 'student', 'content', 'submitted_at', 'grade', 'feedback', 'submitted_at']

class StudentAnswerSerializer(serializers.ModelSerializer):

    class Meta:
        model = StudentAnswer
        fields = ['id', 'submission', 'question', 'answer_text']

class StudentListSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source = 'user.username')
    email = serializers.CharField(source = 'user.email')

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email']

class FundStudentSerializer(serializers.ModelSerializer):
    student_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = Funding
        fields = ['student_id', 'amount']

class FundingStudentSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(source='student.user.username')
    student_email = serializers.CharField(source='student.user.email')

    class Meta:
        model = Funding
        fields = ['id', 'student_username', 'student_email', 'amount', 'status', 'funded_at']

class FundCourseSerializer(serializers.ModelSerializer):
    course_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = Funding
        fields = ['course_id', 'amount']

class FundingHistorySerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = Funding
        fields = ['id', 'sponsor', 'student', 'student_name', 'course', 'course_title', 'amount', 'status', 'funded_at']