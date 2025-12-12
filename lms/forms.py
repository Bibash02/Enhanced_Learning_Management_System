from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from .models import Course, Enrollment, Assignment, Submission, Question, Module, Lesson, UserProfile

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

class UserUpdateForm(forms.ModelForm):
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['image']

class PasswordUpdateForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput, required=False)
    new_password = forms.CharField(widget=forms.PasswordInput, required=False)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=False)

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title', 'description', 'category', 'level', 'price', 'duration_hours', 'thumbnail']

class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = []

class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ["course", "title", "description", "is_published"]
        
        # catch the `user` argument
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)   # remove user before calling super
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            # filter only instructor's courses
            self.fields['course'].queryset = Course.objects.filter(instructor=user)

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = [
            'question_text', 'question_type',
            'option1', 'option2', 'option3', 'option4',
            'correct_option', 'correct_answer', 'essay_guidelines'
        ]

class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['content', 'file']
# class DiscussionForm(forms.ModelForm):
#     class Meta:
#         model = Discussion
#         fields = ['title']

# class CommentForm(forms.ModelForm):
#     class Meta:
#         model = Comment
#         fields = ['content']

class CourseCreateForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title', 'description', 'category', 'level', 'price', 'duration_hours', 'thumbnail', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Course Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Course Description'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '0.01'}),
            'duration_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'thumbnail': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ['title', 'description', 'order']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            # show only courses owned by this instructor
            self.fields['course'].queryset = Course.objects.filter(created_by=user)

class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['module', 'title', 'content', 'duration_minutes', 'video', 'pdf_material', 'order']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # instructor
        course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)

        if course:
            # Only show modules belonging to this course
            self.fields['module'].queryset = Module.objects.filter(course=course)
        elif user:
            # Show all modules of the instructor if course not provided
            self.fields['module'].queryset = Module.objects.filter(course__instructor=user)


class InstructorUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


class InstructorProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile   # or InstructorProfile
        fields = ['image']    # add more fields if you have


class InstructorPasswordForm(PasswordChangeForm):
    pass