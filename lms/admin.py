from django.contrib import admin
from .models import *

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'image', 'role']
    search_fields = ['user']

@admin.register(SponsorProfile)
class SponsorProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'company_name', 'budget']
    search_fields = ['user__username', 'company_name']

@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'instructor', 'category', 'level', 'price', 'is_published']
    list_filter = ['category', 'level', 'is_published']
    search_fields = ['title', 'description']

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'enrolled_at', 'progress']
    list_filter = ['enrolled_at']

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order', 'created_at']
    list_filter = ['course']

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'module', 'order', 'duration_minutes', 'video', 'pdf_material', 'created_at']
    list_filter = ['module__course']

@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ['student', 'lesson', 'status', 'updated_at']
    list_filter = ['status']

# Inline display of questions inside assignment
class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1  # Number of empty question forms to show
    fields = (
        'question_text', 
        'question_type', 
        'option1', 'option2', 'option3', 'option4', 
        'correct_option', 'correct_boolean', 'essay_guidelines'
    )
    readonly_fields = ()
    show_change_link = True

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'created_by', 'created_at', 'is_published']
    list_filter = ['course', 'is_published', 'created_at']
    search_fields = ['title', 'course__title', 'created_by__username']
    inlines = [QuestionInline]

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'assignment', 'grade', 'feedback', 'status', 'submitted_at']
    list_filter = ['assignment__course']

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'time_limit_minutes']
    list_filter = ['course']

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text', 'assignment', 'question_type', 'created_at']
    list_filter = ['question_type', 'assignment__course']
    search_fields = ['question_text']

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['student', 'quiz', 'started_at', 'score']
    list_filter = ['quiz']

# @admin.register(Discussion)
# class DiscussionAdmin(admin.ModelAdmin):
#     list_display = ['title', 'course', 'created_by', 'created_at']
#     list_filter = ['course']
    
# @admin.register(Comment)
# class CommentAdmin(admin.ModelAdmin):
#     list_display = ['author', 'discussion', 'created_at']
#     list_filter = ['discussion__course']

# @admin.register(Checkout)
# class CheckoutAdmin(admin.ModelAdmin):
#     list_display = ['full_name', 'course', 'email', 'address', 'amount', 'payment_status', 'created_at']
#     list_filter = ['full_name', 'course']

@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ['id', 'question', 'submission', 'answer_text']
    list_filter = ['question']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'email', 'phone', 'address', 'course', 'amount', 'payment_type', 'transaction_uuid', 'status', 'created_at']
    list_filter = ['payment_type', 'status', 'created_at']
    search_fields = ['user__username', 'course_name', 'transaction_uuid']
    list_per_page = 5

@admin.register(Funding)
class FundingAdmin(admin.ModelAdmin):
    list_display = ['sponsor', 'student', 'course', 'amount', 'message', 'funded_at']
    list_filter = ['funded_at']
    search_fields = ['sponsor__user__username', 'student__user__username', 'course__title']
    list_per_page = 10