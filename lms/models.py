from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('instructor', 'Instructor'),
        ('sponsor', 'Sponsor')
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='images/', default='images/pic1.jpg')
    #bio = models.TextField(blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

class SponsorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="sponsorprofile")
    budget = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    funding_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    company_name = models.CharField(max_length=255)
    website = models.URLField(blank=True, null=True)
    # add more sponsor-specific fields here

    def __str__(self):
        return self.company_name

class CourseCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name
    class Meta:
        verbose_name_plural = "Course Categories"

class Course(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    title = models.CharField(max_length=200)
    description = models.TextField()
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses_taught')
    category = models.ForeignKey(CourseCategory, on_delete=models.SET_NULL, null=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    duration_hours = models.PositiveIntegerField(default=0)
    thumbnail = models.ImageField(upload_to='course_thumbnails/', blank=True, null=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.title

class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['order']
    def __str__(self):
        return f"{self.course.title} - {self.title}"

class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='course_lessons', blank=True, null=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='module_lessons')
    title = models.CharField(max_length=200)
    content = models.TextField()
    video = models.FileField(upload_to='lessons/videos', blank=True, null=True)
    pdf_material = models.FileField(upload_to='lessons/pdfs', blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        unique_together = ('module', 'title')

    def __str__(self):
        return f"{self.module.title if self.module else 'No Module'} - {self.title}"

class StudentLessonCompletion(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    lesson = models.ForeignKey('Lesson', on_delete=models.CASCADE)
    enrollment = models.ForeignKey('Enrollment', on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'lesson')  # avoid duplicate completion

class LessonProgress(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'lesson')

class Assignment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assignments', null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateTimeField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignments', null=True, blank=True)
    max_points = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.course.title} - {self.title}"

class Quiz(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    time_limit_minutes = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.course.title} - {self.title}"

class Question(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, null=True, blank=True, related_name='questions')
    QUESTION_TYPES = [
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer'),
    ]
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions', null=True, blank=True)
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    points = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)

    # Multiple-choice specific fields
    option1 = models.CharField(max_length=200, blank=True, null=True)
    option2 = models.CharField(max_length=200, blank=True, null=True)
    option3 = models.CharField(max_length=200, blank=True, null=True)
    option4 = models.CharField(max_length=200, blank=True, null=True)
    correct_option = models.CharField(max_length=1, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')], blank=True, null=True)
    
    # True/False specific
    correct_answer = models.BooleanField(default=True, blank=True)  # True or False
    
    # Essay specific (optional: add word limit or instructions)
    word_limit = models.PositiveIntegerField(default=0, blank=True, null=True)
    essay_guidelines = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
    def __str__(self):
        return self.question_text[:50]

class Submission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('graded', 'Graded'),
        ('late', 'Late'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    content = models.TextField()
    file = models.FileField(upload_to='submissions/', blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    grade = models.PositiveIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    def __str__(self):
        return f"{self.student.username}"
    
class StudentAnswer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    submission = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_answers')  # student who submitted
    answer_text = models.TextField()

    def __str__(self):
        # question has no `title` field; use a slice of `question_text` to avoid attribute errors
        q_text = self.question.question_text if self.question and self.question.question_text else ''
        return f"{self.submission.username} - {q_text[:50]}"
    
class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    choice_text = models.CharField(max_length=200)
    is_correct = models.BooleanField(default=False)
    def __str__(self):
        return self.choice_text
    
class QuizAttempt(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    score = models.PositiveIntegerField(default=0)
    def __str__(self):
        return f"{self.student.username} - {self.quiz.title}"

# class Discussion(models.Model):
#     course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='discussions')
#     title = models.CharField(max_length=200)
#     created_by = models.ForeignKey(User, on_delete=models.CASCADE)
#     created_at = models.DateTimeField(auto_now_add=True)
#     def __str__(self):
#         return self.title

# class Comment(models.Model):
#     discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name='comments')
#     author = models.ForeignKey(User, on_delete=models.CASCADE)
#     content = models.TextField()
#     created_at = models.DateTimeField(auto_now_add=True)
#     parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
#     def __str__(self):
#         return f"Comment by {self.author.username} on {self.discussion.title}"

class Sponsorship(models.Model):
    sponsor = models.ForeignKey(SponsorProfile, on_delete=models.CASCADE, related_name="sponsorships")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="funded_by")
    course = models.ForeignKey("Course", on_delete=models.CASCADE, related_name="funded_courses")
    funded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        unique_together = ("sponsor", "student", "course")

    def __str__(self):
        return f"{self.sponsor} funds {self.student} for {self.course.title}"

class StudentProgress(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    progress = models.FloatField(default=0)  # percentage
    last_updated = models.DateTimeField(auto_now=True)

class StudentLessonCompletion(models.Model):
    pass

    
# class Checkout(models.Model):
#     PAYMENT_CHOICES = [
#         ('cod', 'Cash on Delivery'),
#         ('esewa', 'eSewa'),
#     ]

#     user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
#     full_name = models.CharField(max_length=200)
#     email = models.EmailField()
#     phone = models.CharField(max_length=20, blank=True, null=True)
#     address = models.TextField()
#     course = models.CharField(max_length=255)
#     amount = models.FloatField()
#     payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='cod')
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.full_name} - {self.course}"

class Enrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    hours_spent = models.IntegerField(default=0)
    progress = models.PositiveIntegerField(default=0)  # Percentage

    class Meta:
        unique_together = ['student', 'course']
    def __str__(self):
        return f"{self.student.username} - {self.course.title}"

class Order(models.Model):
    PAYMENT_TYPES = (
        ('esewa', 'eSewa'),
        ('cod', 'Cash on Delivery'),
    )

    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
        ('Cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey("Course", on_delete=models.CASCADE, blank=True, null=True)

    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default="Nepal")

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")

    # You generate this UUID before sending to eSewa
    transaction_uuid = models.CharField(max_length=255, unique=True)

    # eSewa sends this after successful payment → refId
    transaction_ref_id = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"

class Funding(models.Model):
    sponsor = models.ForeignKey(User, on_delete=models.CASCADE)
    student = models.ForeignKey(UserProfile, null=True, blank=True, on_delete=models.CASCADE, related_name='fundings')
    course = models.ForeignKey(Course, null=True, blank=True, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    message = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default="Pending")
    funded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.course:
            return f"{self.sponsor.username} funded course {self.course.title} - {self.amount}"
        else:
            return f"{self.sponsor.username} funded student {self.student.user.username} - {self.amount}"
    
