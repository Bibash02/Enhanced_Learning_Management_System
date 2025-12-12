from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Q, Count, Avg, Min
from django.utils import timezone
from .models import *
from .forms import *
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, logout, authenticate
from django.db.models import Sum
import uuid
from django.db import IntegrityError
from django.core.paginator import Paginator
from decimal import Decimal
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import uuid
import hmac
import hashlib
import base64
import json
from django.conf import settings
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.dispatch import receiver
from django.contrib.auth import update_session_auth_hash

def signup(request):
    if request.method == "POST":
        fullname = request.POST.get("fullname")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        role = request.POST.get("role")
        image = request.FILES.get("image")

        if password != confirm_password:
            messages.error(request, "Password do not match!")
            return redirect('signup')

        if User.objects.filter(username=email).exists():
            messages.error(request, "Email already exists!")
            return redirect('signup')
        
        if role not in ['student', 'instructor', 'sponsor']:
            messages.error(request, "Please select a valid role.")
            return redirect('signup')

        user = User.objects.create_user(
            username=email, email=email, password=password, first_name=fullname
        )
        user.save()

        UserProfile.objects.create(user = user, role = role, image=image if image else "images/default.jpg")

        # Create sponsor profile if user is sponsor
        if role == "sponsor":
            SponsorProfile.objects.create(
                user=user,
                budget=0,
                company_name="",
                website=None,
            )

        messages.success(request, "Account created Successfully.")
        return redirect('signin')
    return render(request, 'signup.html')

def     signin(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user_obj = User.objects.get(email = email)
            user = authenticate(request, username = user_obj.username, password = password)
        except User.DoesNotExist:
            user = None

        if user is not None:
            login(request, user)

            # get role from userprofile
            role = user.userprofile.role
            if role == 'student':
                return redirect('student_dashboard')
            elif role == 'instructor':
                return redirect('instructor_dashboard')
            elif role == 'sponsor':
                return redirect('sponsor_dashboard')
            else:
                return redirect('signup')
        else:
            messages.error(request, "Invalid email or password!")
            return redirect('signin')
    return render(request, 'signin.html')


def signout(request):
    logout(request)
    messages.success(request, "Logout successfully.")
    return redirect('home')

def home(request):
    categories = CourseCategory.objects.all()
    featured_courses = Course.objects.filter(is_published=True)[:6]
    popular_courses = Course.objects.filter(is_published=True).annotate(
        enrollment_count=Count('enrollments')
    ).order_by('-enrollment_count')[:6]
    context = {
        'categories': categories,
        'featured_courses': featured_courses,
        'popular_courses': popular_courses,
    }
    return render(request, 'home.html', context)

def course_list(request):
    courses = Course.objects.filter(is_published=True)

    # Filters
    category = request.GET.get('category')
    level = request.GET.get('level')
    search = request.GET.get('search')

    if category:
        courses = courses.filter(category__id=category)  # use ID for matching
    if level:
        courses = courses.filter(level=level)
    if search:
        courses = courses.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(instructor__first_name__icontains=search) |
            Q(instructor__last_name__icontains=search)
        )

    # Pagination
    paginator = Paginator(courses, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "categories": CourseCategory.objects.all(),
        "selected_category": category,
        "selected_level": level,
        "search_query": search,
    }
    return render(request, 'course_list.html', context)

@login_required
def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id, is_published=True)
    modules = course.modules.prefetch_related('lessons').order_by('order')

    # Check if user is enrolled
    enrolled = Enrollment.objects.filter(student=request.user, course=course).exists()

    # Total sponsorship funding for this course
    total_funded = Funding.objects.filter(
        course=course,
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Discounted price calculation
    discounted_price = float(course.price) - float(total_funded)
    if discounted_price < 0:
        discounted_price = 0

    # Handle enrollment POST request
    if request.method == 'POST' and not enrolled:
        Enrollment.objects.create(student=request.user, course=course)
        return redirect('course_detail', course_id=course.id)

    context = {
        'course': course,
        'modules': modules,
        'enrolled': enrolled,
        'total_funded': total_funded,          # NEW
        'discounted_price': discounted_price,  # NEW
    }

    return render(request, 'course_detail.html', context)


# @login_required
# def enroll_course(request, course_id):
#     course = get_object_or_404(Course, id=course_id, is_published=True)
    
#     if Enrollment.objects.filter(student=request.user, course=course).exists():
#         messages.warning(request, 'You are already enrolled in this course.')
#     else:
#         Enrollment.objects.create(student=request.user, course=course)
#         messages.success(request, f'Successfully enrolled in {course.title}')
    
#     return redirect('course_detail', course_id=course_id)

def course_content(request, course_id):
    course = get_object_or_404(Course, id=course_id, is_published=True)
    
    # Check enrollment and instructor status
    enrollment = Enrollment.objects.filter(course=course, student=request.user).first()
    is_instructor = course.instructor == request.user
    is_enrolled = enrollment is not None
    
    # For non-enrolled, non-instructor: Show enroll prompt (no full content)
    if not is_enrolled and not is_instructor:
        context = {
            'course': course,
            'can_enroll': True,
            'breadcrumb': [{'name': 'Dashboard', 'url': 'student_dashboard'}, {'name': course.title, 'active': True}],
        }
        return render(request, 'course_detail.html', context)
    
    # Fetch lessons (content for learning)
    lessons = course.lessons.select_related().order_by('order')
    total_lessons = lessons.count()

    # Calculate progress for enrolled users
    if is_enrolled:
        completed_lessons = StudentLessonCompletion.objects.filter(
            enrollment=enrollment, is_completed=True
        ).count()
        course_progress = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
        
        # Update enrollment progress
        enrollment.progress = course_progress
        enrollment.save()
        
        # Handle POST: Mark lesson complete (for learning progress)
        if request.method == 'POST':
            lesson_id = request.POST.get('lesson_id')
            if lesson_id:
                lesson = get_object_or_404(Lesson, id=lesson_id, course=course)
                completion, created = StudentLessonCompletion.objects.get_or_create(
                    enrollment=enrollment, 
                    lesson=lesson, 
                    defaults={'is_completed': True}
                )
                if created:
                    messages.success(request, f'"{lesson.title}" completed! Progress updated.')
                return redirect('course_detail', course_id=course.id)
    else:
        # For instructors (no enrollment needed)
        course_progress = 0
        completed_lessons = 0
    
    # Fetch pending assignments (for quizzes/homework)
    assignments = Assignment.objects.filter(
        course=course, 
        due_date__gte=timezone.now()
    ).order_by('due_date')
    
    context = {
        'course': course,
        'enrollment': enrollment,
        'lessons': lessons,
        'assignments': assignments,
        'course_progress': course_progress,
        'completed_lessons': completed_lessons,
        'total_lessons': total_lessons,
        'is_instructor': is_instructor,
        'is_enrolled': is_enrolled,
        'breadcrumb': [{'name': 'Dashboard', 'url': 'student_dashboard' if not is_instructor else 'instructor_dashboard'}, 
                       {'name': course.title, 'active': True}],
    }
    return render(request, 'course_detail.html', context)

# @login_required
# def course_content(request, course_id):
#     course = get_object_or_404(Course, id=course_id, is_published=True)
    
#     # Check enrollment and instructor status
#     enrollment = Enrollment.objects.filter(course=course, student=request.user).first()
#     is_instructor = course.instructor == request.user
#     is_enrolled = enrollment is not None
    
#     # Non-enrolled, non-instructor: show enroll prompt
#     if not is_enrolled and not is_instructor:
#         context = {
#             'course': course,
#             'can_enroll': True,
#             'breadcrumb': [
#                 {'name': 'Dashboard', 'url': 'student_dashboard'},
#                 {'name': course.title, 'active': True}
#             ],
#         }
#         return render(request, 'course_detail.html', context)
    
#     # Fetch lessons (use related_name from Lesson model)
#     lessons = course.course_lessons.select_related('module').order_by('order')
#     total_lessons = lessons.count()

#     # Calculate progress for enrolled users
#     course_progress = 0
#     completed_lessons = 0
#     if is_enrolled:
#         completed_lessons = StudentLessonCompletion.objects.filter(
#             enrollment=enrollment, is_completed=True
#         ).count()
#         course_progress = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
        
#         # Update enrollment progress
#         enrollment.progress = course_progress
#         enrollment.save()
        
#         # Handle POST: mark lesson complete
#         if request.method == 'POST':
#             lesson_id = request.POST.get('lesson_id')
#             if lesson_id:
#                 lesson = get_object_or_404(Lesson, id=lesson_id, course=course)
#                 completion, created = StudentLessonCompletion.objects.get_or_create(
#                     enrollment=enrollment,
#                     lesson=lesson,
#                     defaults={'is_completed': True}
#                 )
#                 if created:
#                     messages.success(request, f'"{lesson.title}" complete! Progress updated.')
#                 return redirect('course_content', course_id=course.id)
#     else:
#         # For instructors (no enrollment needed)
#         course_progress = 0
#         completed_lessons = 0
    
#     # Fetch upcoming assignments
#     assignments = Assignment.objects.filter(
#         course=course,
#         due_date__gte=timezone.now()
#     ).order_by('due_date')
    
#     context = {
#         'course': course,
#         'enrollment': enrollment,
#         'lessons': lessons,
#         'assignments': assignments,
#         'course_progress': course_progress,
#         'completed_lessons': completed_lessons,
#         'total_lessons': total_lessons,
#         'is_instructor': is_instructor,
#         'is_enrolled': is_enrolled,
#         'breadcrumb': [
#             {'name': 'Dashboard', 'url': 'student_dashboard' if not is_instructor else 'instructor_dashboard'},
#             {'name': course.title, 'active': True}
#         ],
#     }
#     return render(request, 'course_detail.html', context)


@login_required
def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(Lesson.objects.select_related('module', 'course'), id=lesson_id)
    course = lesson.course or lesson.module.course

    # Check enrollment
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        return redirect(f"/checkout/?course_id={course.id}")

    # Sidebar
    modules = course.modules.prefetch_related('module_lessons')

    # Mark lesson as "In Progress"
    progress, created = LessonProgress.objects.get_or_create(student=request.user, lesson=lesson)
    if progress.status == "Not Started":
        progress.status = "In Progress"
        progress.save()

    # Previous and next lessons
    lessons_in_module = list(lesson.module.module_lessons.all().order_by('order'))
    current_index = lessons_in_module.index(lesson)
    previous_lesson = lessons_in_module[current_index - 1] if current_index > 0 else None
    next_lesson = lessons_in_module[current_index + 1] if current_index < len(lessons_in_module) - 1 else None

    # Fetch progress for all lessons in the course
    lesson_progress_qs = LessonProgress.objects.filter(
        student=request.user,
        lesson__module__course=course
    )
    progress_map = {p.lesson.id: p.status for p in lesson_progress_qs}

    # Calculate course progress %
    total_lessons = Lesson.objects.filter(module__course=course).count()
    completed_lessons = lesson_progress_qs.filter(status="Completed").count()
    progress_percent = int((completed_lessons / total_lessons) * 100) if total_lessons else 0

    context = {
    "course": course,
    "modules": modules,
    "selected_lesson": lesson,
    "previous_lesson": previous_lesson,
    "next_lesson": next_lesson,
    "progress_map": progress_map,
    "progress_percent": progress_percent,
    }
    return render(request, "lesson_detail.html", context)

@login_required
def assignment_list(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)
    assignments = course.assignments.all()
    context = {
        'course': course,
        'assignments': assignments,
        'enrollment': enrollment,
    }
    return render(request, 'assignment_list.html', context)

@login_required
def assignment_detail(request, course_id, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id, course_id=course_id)
    submission = Submission.objects.filter(assignment=assignment, student=request.user).first()
    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            if submission:
                submission.content = form.cleaned_data['content']
                submission.file = form.cleaned_data['file'] or submission.file
                submission.save()
                messages.success(request, 'Submission updated successfully!')
            else:
                submission = form.save(commit=False)
                submission.assignment = assignment
                submission.student = request.user
                submission.save()
                messages.success(request, 'Assignment submitted successfully!')
            return redirect('assignment_detail', course_id=course_id, assignment_id=assignment_id)
    else:
        form = SubmissionForm(instance=submission)
    context = {
        'assignment': assignment,
        'submission': submission,
        'form': form,
    }
    return render(request, 'assignment_detail.html', context)

@login_required
def assignment_delete(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    if request.user == assignment.created_by:  # ensure only creator can delete
        assignment.delete()
        messages.success(request, "Assignment deleted successfully.")
    else:
        messages.error(request, "You do not have permission to delete this assignment.")
    return redirect('instructor_dashboard')

#@login_required
# def discussion_list(request, course_id):
#     course = get_object_or_404(Course, id=course_id)
#     discussions = course.discussions.prefetch_related('comments').all()
#     if request.method == 'POST':
#         form = DiscussionForm(request.POST)
#         if form.is_valid():
#             discussion = form.save(commit=False)
#             discussion.course = course
#             discussion.created_by = request.user
#             discussion.save()
#             messages.success(request, 'Discussion created successfully!')
#             return redirect('discussion_list', course_id=course_id)
#     else:
#         form = DiscussionForm()
#     context = {
#         'course': course,
#         'discussions': discussions,
#         'form': form,
#     }
#     return render(request, 'discussion_list.html', context)

# @login_required
# def discussion_detail(request, course_id, discussion_id):
#     discussion = get_object_or_404(Discussion, id=discussion_id, course_id=course_id)
#     if request.method == 'POST':
#         form = CommentForm(request.POST)
#         if form.is_valid():
#             comment = form.save(commit=False)
#             comment.discussion = discussion
#             comment.author = request.user
#             comment.save()
#             messages.success(request, 'Comment added successfully!')
#             return redirect('discussion_detail', course_id=course_id, discussion_id=discussion_id)
#     else:
#         form = CommentForm()
#     context = {
#         'discussion': discussion,
#         'form': form,
#     }
#     return render(request, 'discussion_detail.html', context)

@login_required
def student_dashboard(request):
    user = request.user

    # Enrollments
    enrollments = Enrollment.objects.filter(student=user).select_related('course')
    enrolled_courses_count = enrollments.count()
    completed_courses_count = enrollments.filter(completed=True).count()

    # 1. Get enrolled course IDs
    enrolled_course_ids = enrollments.values_list('course_id', flat=True)

    # 2. Get assignments of those courses
    assignments = Assignment.objects.filter(course_id__in=enrolled_course_ids)

    # 3. Get student submissions
    submitted_assignments = Submission.objects.filter(
        student=user
    ).values_list('assignment_id', flat=True)

    # 4. Pending assignments (same as your working page)
    pending_assignments = assignments.exclude(id__in=submitted_assignments)

    # 5. Count
    pending_assignments_count = pending_assignments.count()

    # Total hours spent
    total_hours_spent = enrollments.aggregate(
        total=Sum('hours_spent')
    )['total'] or 0

    context = {
        'enrollments': enrollments,
        'enrolled_courses_count': enrolled_courses_count,
        'completed_courses_count': completed_courses_count,
        'pending_assignments_count': pending_assignments_count,
        'pending_assignments': pending_assignments,
        'total_hours_spent': total_hours_spent,
    }
    return render(request, 'student_dashboard.html', context)


@login_required
def instructor_dashboard(request):
    user = request.user
    courses = Course.objects.filter(instructor=user)
    total_courses = courses.count()
    total_students = Enrollment.objects.filter(course__in=courses).values('student').distinct().count()
    total_assignments = sum(course.assignments.count() for course in courses)

    # Optionally, fetch recent assignments for quick access (limit 5)
    recent_assignments = []
    for course in courses:
        recent_assignments.extend(course.assignments.all().order_by('-created_at')[:5])
    # Sort all recent assignments by created_at descending
    recent_assignments = sorted(recent_assignments, key=lambda a: a.created_at, reverse=True)[:5]

    context = {
        'courses': courses,
        'total_courses': total_courses,
        'total_students': total_students,
        'total_assignments': total_assignments,
        'recent_assignments': recent_assignments,
    }
    return render(request, 'instructor_dashboard.html', context)

def sponsor_dashboard(request):
    sponsor = request.user

    # Get funded UserProfile students
    sponsored_students = UserProfile.objects.filter(
        fundings__sponsor=sponsor,
        role="student"
    ).annotate(
        amount_sponsored=Sum("fundings__amount"),
        first_sponsored_date=Min("fundings__funded_at"),
        enrolled_courses=Count("user__enrollments", distinct=True),
        avg_progress=Avg("user__enrollments__progress"),
    ).distinct()

    # Total funds calculated
    total_funds = Funding.objects.filter(
        sponsor=sponsor,
        student__isnull=False
    ).aggregate(total=Sum("amount"))["total"] or 0

    fundings = Funding.objects.filter(sponsor=sponsor).select_related("course")

    context = {
        "sponsor_name": sponsor.username,
        "sponsored_students": sponsored_students,
        "total_students_sponsored": sponsored_students.count(),
        "total_funds_allocated": total_funds,
        "remaining_balance": 0,  # add your wallet system here
        "ongoing_sponsorships": sponsored_students.count(),
        "fundings": fundings,
    }
    return render(request, "sponsor_dashboard.html", context)

@login_required
def sponsor_profile(request):
    sponsor = request.user  
    context = {
        "sponsor_name": sponsor.get_full_name() or sponsor.username,
    }
    return render(request, 'sponsor_profile.html', context)

@login_required
def update_sponosr_profile(request):
    return render(request, 'update_sponsor_profile.html')

def renew_sponsorship(request, student_id):
    pass

@login_required
def student_profile_view(request, student_id):

    student_profile = get_object_or_404(UserProfile, id=student_id)

    # Student user (Django auth user)
    student_user = student_profile.user

    # All courses the student is enrolled in
    enrolled_courses = Enrollment.objects.filter(student=student_user)

    # Funding history from this sponsor to this student
    sponsor = request.user
    funding_history = Funding.objects.filter(
        sponsor=sponsor,
        student=student_profile
    )

    # Total funding provided
    total_funded_amount = funding_history.aggregate(total=Sum("amount"))['total'] or 0

    context = {
        "student_profile": student_profile,
        "student_user": student_user,
        "enrolled_courses": enrolled_courses,
        "funding_history": funding_history,
        "total_funded_amount": total_funded_amount,
    }

    return render(request, "student_profile_view.html", context)

def funding_history(request):
    sponsor = request.user

    # Get all fundings made by this sponsor
    fundings_list = Funding.objects.filter(sponsor=sponsor).order_by('-funded_at')

    # ---------------- Pagination ----------------
    paginator = Paginator(fundings_list, 10)  # 10 items per page
    page_number = request.GET.get('page', 1)
    try:
        fundings = paginator.page(page_number)
    except PageNotAnInteger:
        fundings = paginator.page(1)
    except EmptyPage:
        fundings = paginator.page(paginator.num_pages)
    # -------------------------------------------

    context = {
        "sponsor_name": sponsor.get_full_name() or sponsor.username,
        "fundings": fundings,
    }
    return render(request, "funding_history.html", context)

# Fund a student
@login_required
def fund_student(request):
    # Ensure only sponsors can access this page
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'sponsor':
            messages.error(request, "You do not have permission to access this page.")
            return redirect('sponsor_dashboard')  # Or appropriate redirect
    except UserProfile.DoesNotExist:
        messages.error(request, "Profile not found.")
        return redirect('signin')
    
    # Get active students (role='student')
    students = UserProfile.objects.filter(role='student', user__is_active=True)
    
    context = {
        'students': students,
        'sponsor_name': user_profile.user.first_name or user_profile.user.username,  # Fallback to username
    }
    return render(request, 'fund_student.html', context)

@login_required
def fund_student_detail(request, student_id):
    user = request.user

    # Check if the logged-in user is a sponsor
    if not hasattr(user, 'sponsorprofile'):
        return HttpResponse("You are not authorized. Sponsor account required.", status=403)

    sponsor = user.sponsorprofile
    student = get_object_or_404(User, id=student_id)

    if request.method == "POST":
        amount = request.POST.get('amount')
        course_id = request.POST.get('course')

        Sponsorship.objects.create(
            sponsor=sponsor,
            student=student,
            course_id=course_id,
            funded_amount=amount
        )
        return redirect('sponsor_dashboard')

    courses = student.enrollments.all()
    return render(request, 'fund_student_detail.html', {
        'student': student,
        'courses': courses,
        'sponsor': sponsor
    })

@login_required
def fund_student_action(request, student_id):
    # Ensure only sponsors can fund
    try:
        sponsor_profile = request.user.userprofile
        if sponsor_profile.role != 'sponsor':
            messages.error(request, "You do not have permission to fund students.")
            return redirect('fund_student')
    except UserProfile.DoesNotExist:
        messages.error(request, "Profile not found.")
        return redirect('signin')
    
    if request.method == 'POST':
        student_profile = get_object_or_404(UserProfile, id=student_id, role='student')
        amount = request.POST.get('amount')  # Assuming amount is input in the form
        
        if not amount or float(amount) <= 0:
            messages.error(request, "Please enter a valid amount.")
            return redirect('fund_student')
        
        amount = float(amount)
        
        # Check if sponsor has sufficient balance (optional, if tracking funds)
        if sponsor_profile.funding_balance is not None and sponsor_profile.funding_balance < amount:
            messages.error(request, "Insufficient funds.")
            return redirect('fund_student')
        
        # Create sponsorship record
        Sponsorship.objects.create(
            sponsor=sponsor_profile,
            student=student_profile,
            amount=amount,
            # course=some_course if specifying a course
        )
        
        # Deduct from sponsor's balance (if applicable)
        if sponsor_profile.funding_balance is not None:
            sponsor_profile.funding_balance -= amount
            sponsor_profile.save()
        
        messages.success(request, f"You have funded {student_profile.user.first_name} {student_profile.user.last_name} for ${amount}!")
        return redirect('fund_student')
    
    return redirect('fund_student')  # Handle non-POST requests

@login_required
def fund_course_action(request, student_id):
    sponsor = request.user.sponsorprofile
    student = get_object_or_404(User, id=student_id)

    amount = Decimal(request.POST.get("amount"))

    # Check sufficient balance
    if sponsor.funding_balance < amount:
        messages.error(request, "Insufficient balance!")
        return redirect('fund_student_detail', student_id=student_id)

    # Deduct sponsor balance
    sponsor.funding_balance -= amount
    sponsor.save()

    # Create funding entry (Sponsorship model)
    Sponsorship.objects.create(
        sponsor=sponsor,
        student=student,
        funded_amount=amount
    )

    messages.success(request, f"Successfully funded {amount} to {student.first_name}")
    return redirect('sponsor_dashboard')


# @login_required
# def fund_course_page(request):
#     # Get all courses
#     courses = Course.objects.all()

#     # Get the sponsor profile for the logged-in user
#     try:
#         user_profile = UserProfile.objects.get(user=request.user, role='sponsor')
#         sponsor_name = request.user.get_full_name()  # or request.user.username if you prefer
#     except UserProfile.DoesNotExist:
#         sponsor_name = "Sponsor"  # fallback if somehow profile not found

#     context = {
#         "courses": courses,
#         "sponsor_name": sponsor_name,
#     }

#     return render(request, "fund_course_page.html", context)

@login_required
def fund_course_page(request):
    sponsor = request.user
    sponsor_profile = UserProfile.objects.get(user=sponsor)

    # Get all published courses
    courses = Course.objects.filter(is_published=True)

    context = {
        "sponsor_username": sponsor.get_full_name() or sponsor.username,
        "courses": courses,
    }
    return render(request, "fund_course_page.html", context)

@login_required
def fund_course_checkout(request, course_id):
    """
    Checkout page for funding a course.
    """
    course = get_object_or_404(Course, id=course_id, is_published=True)

    if request.method == "POST":
        amount = request.POST.get("amount")
        if not amount or float(amount) <= 0:
            messages.error(request, "Enter a valid funding amount.")
            return redirect('fund_course_checkout', course_id=course.id)

        # Redirect to eSewa payment processing
        return redirect('fund_course_payment_process', course_id=course.id)

    context = {
        "course": course,
        "amount": course.price
    }
    return render(request, "fund_course_checkout.html", context)

@login_required
def fund_course_payment_process(request, course_id):
    sponsor = request.user
    course = get_object_or_404(Course, id=course_id, is_published=True)

    if request.method == "POST":
        amount = request.POST.get("amount")
        if not amount or float(amount) <= 0:
            messages.error(request, "Invalid funding amount.")
            return redirect("fund_course_checkout", course_id=course_id)

        # =======================
        # 1. Create Funding entry
        # =======================
        funding = Funding.objects.create(
            sponsor=sponsor,
            course=course,
            amount=amount,
            status="Pending",
            funded_at=timezone.now()
        )

        # =======================
        # 2. Create Order entry
        # =======================
        transaction_uuid = str(uuid.uuid4())

        order = Order.objects.create(
            user=sponsor,
            course=course,
            full_name=sponsor.get_full_name() or sponsor.username,
            email=sponsor.email,
            phone="N/A",
            address="Online Funding",
            city="N/A",
            country="Nepal",
            amount=amount,
            payment_type="esewa",
            status="Pending",
            transaction_uuid=transaction_uuid,
        )

        # =======================
        # 3. eSewa Signature Logic
        # =======================
        product_code = settings.ESEWA_PRODUCT_CODE
        secret_key = settings.ESEWA_SECRET_KEY

        data_string = (
            f"total_amount={amount},"
            f"transaction_uuid={transaction_uuid},"
            f"product_code={product_code}"
        )

        signature = base64.b64encode(
            hmac.new(secret_key.encode(), data_string.encode(), hashlib.sha256).digest()
        ).decode()

        # =======================
        # 4. Success / Failure URLs
        # =======================
        success_url = request.build_absolute_uri(
            reverse("fund_course_esewa_success", args=[order.id])
        )
        failure_url = request.build_absolute_uri(
            reverse("fund_course_esewa_fail", args=[order.id])
        )

        # =======================
        # 5. Render Auto-submit Form
        # =======================
        context = {
            "order": order,
            "course": course,
            "total_amount": amount,
            "transaction_uuid": transaction_uuid,
            "product_code": product_code,
            "signature": signature,
            "success_url": success_url,
            "failure_url": failure_url,
        }

        return render(request, "fund_course_process.html", context)

    return redirect("fund_course_page")

@login_required
def fund_course_esewa_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # eSewa returns refId
    refId = request.GET.get("refId")

    if not refId:
        messages.error(request, "Payment verification failed! Missing refId.")
        return redirect("fund_course_page")

    # Mark order as completed
    order.status = "Completed"
    order.transaction_ref_id = refId
    order.save()

    # Update funding entry
    funding = Funding.objects.filter(
        sponsor=order.user, course=order.course, amount=order.amount
    ).first()

    if funding:
        funding.status = "Completed"
        funding.save()

    instructor = order.course.instructor
    sponsor = order.user
    course = order.course

    if instructor and instructor.email:
        subject = "Your Course Has Received a Sponsorship!"
        message = (
            f"Hello {instructor.get_full_name() or instructor.username},\n\n"
            f"Your course \"{course.title}\" has received a sponsorship.\n"
            f"Sponsor: {sponsor.get_full_name() or sponsor.username}\n"
            f"Amount Funded: Rs. {order.amount}\n\n"
            "Now, Good Care of the Fund.\n\n"
            "Best regards,\n"
            "Your Sponsor"
        )

        send_mail(
            subject,
            message,
            "noreply@lmspro.com",
            [instructor.email],
            fail_silently=True
        )

    messages.success(request, f"Successfully funded course: {order.course.title}")
    return redirect("fund_course_page")


@login_required
def fund_course_esewa_fail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order.status = "Failed"
    order.save()

    funding = Funding.objects.filter(
        sponsor=order.user,
        course=order.course,
        amount=order.amount
    ).first()

    if funding:
        funding.status = "Failed"
        funding.save()

    messages.error(request, f"Payment failed for course: {order.course.title}")
    return redirect("fund_course_page")


@login_required
def course_create(request):
    if request.method == 'POST':
        form = CourseCreateForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            course.instructor = request.user  # Set current user as instructor
            course.save()
            return redirect('instructor_dashboard')
    else:
        form = CourseCreateForm()

    return render(request, 'course_create.html', {'form': form})

@login_required
def course_edit(request, course_id):
    course = get_object_or_404(Course, id=course_id, instructor=request.user)
    
    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, 'Course updated successfully!')
            return redirect('instructor_dashboard')
    else:
        form = CourseForm(instance=course)
    
    context = {
        'form': form,
        'course': course,
    }
    return render(request, 'course_edit.html', context)

def course_delete(request, course_id):
    course = get_object_or_404(Course, id = course_id, instructor = request.user)

    if request.method == "POST":
        course.delete()
        messages.success(request, "Course deleted successfully.")
        return redirect('instructor_dashboard')
    return render(request, 'course_delete.html', {"course": course})

@login_required
def assignment_create(request):
    if request.method == 'POST':
        form = AssignmentForm(request.POST, request.FILES)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.created_by = request.user

            # Get due_date from POST (optional)
            due_date_input = request.POST.get('due_date')
            if due_date_input:
                # Convert string from datetime-local input to Python datetime
                from datetime import datetime
                assignment.due_date = datetime.strptime(due_date_input, "%Y-%m-%dT%H:%M")
            
            assignment.save()

            # Detect question type
            q_type = request.POST.get('question_type')

            if q_type == 'true_false':
                Question.objects.create(
                    assignment=assignment,
                    question_type='true_false',
                    question_text=request.POST.get('true_false_question'),
                    correct_boolean=True if request.POST.get('true_false_answer') == 'True' else False
                )

            elif q_type == 'mcq':
                Question.objects.create(
                    assignment=assignment,
                    question_type='mcq',
                    question_text=request.POST.get('mcq_question'),
                    option1=request.POST.get('mcq_option1'),
                    option2=request.POST.get('mcq_option2'),
                    option3=request.POST.get('mcq_option3'),
                    option4=request.POST.get('mcq_option4'),
                    correct_option=request.POST.get('mcq_correct')
                )

            elif q_type == 'essay':
                Question.objects.create(
                    assignment=assignment,
                    question_type='essay',
                    question_text=request.POST.get('essay_question'),
                    essay_guidelines=request.POST.get('essay_guidelines')
                )

            enrolled_students = Enrollment.objects.filter(course=assignment.course)

            subject = "New Assignment Posted"
            message = (
                f"Hello Student,\n\n"
                f"A new assignment has been created in the course: {assignment.course.title}\n\n"
                f"Title: {assignment.title}\n"
                f"Due Date: {assignment.due_date}\n\n"
                f"Please log in to complete the assignment on time.\n\n"
                "Best regards,\n"
                "Your Instructor"
            )

            for enroll in enrolled_students:
                student_email = enroll.student.email
                if student_email:
                    send_mail(
                        subject,
                        message,
                        "instructor@example.com",
                        [student_email],
                        fail_silently=True  
                    )

            messages.success(request, "Assignment created successfully!")
            return redirect('instructor_dashboard')

        else:
            messages.error(request, "Please correct the errors below.")

    else:
        form = AssignmentForm()

    return render(request, 'assignment_create.html', {'form': form})

@login_required
def course_learn(request, course_id, lesson_id=None):
    course = get_object_or_404(Course, pk=course_id)
    modules = course.modules.prefetch_related('module_lessons')

    # Preload all progress for this user
    user_progress_qs = LessonProgress.objects.filter(student=request.user, lesson__module__course=course)
    progress_map = {p.lesson_id: p.status for p in user_progress_qs}

    # Count all lessons and completed lessons
    all_lessons = Lesson.objects.filter(module__course=course)
    total_lessons = all_lessons.count()
    completed_lessons = sum(1 for l in all_lessons if progress_map.get(l.id) == 'completed')
    progress_percent = round((completed_lessons / total_lessons) * 100) if total_lessons > 0 else 0

    selected_lesson = None
    if lesson_id:
        selected_lesson = get_object_or_404(Lesson, id=lesson_id)

        # Auto mark as in_progress if not started
        progress_obj, created = LessonProgress.objects.get_or_create(
            student=request.user,
            lesson=selected_lesson,
            defaults={'status': 'in_progress'}
        )
        if not created and progress_obj.status == 'not_started':
            progress_obj.status = 'in_progress'
            progress_obj.save()

        progress_map[selected_lesson.id] = progress_obj.status

    context = {
        'course': course,
        'modules': modules,
        'selected_lesson': selected_lesson,
        'progress_percent': progress_percent,
        'progress_map': progress_map,
        'completed_lessons': completed_lessons,
        'total_lessons': total_lessons,
    }

    return render(request, 'course_learn.html', context)

@login_required
def mark_lesson_completed(request, lesson_id):
    lesson = get_object_or_404(Lesson.objects.select_related('module', 'course'), id=lesson_id)
    
    # Ensure student is enrolled
    course = lesson.course or lesson.module.course
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        return redirect(f"/checkout/?course_id={course.id}")
    
    progress, created = LessonProgress.objects.get_or_create(student=request.user, lesson=lesson)
    progress.status = "Completed"
    progress.save()
    
    return redirect('lesson_detail', lesson_id=lesson.id)

def assignment_edit(request, assignment_id):
    pass


def create_module(request, course_id):
    course = get_object_or_404(Course, id = course_id, instructor = request.user)

    if request.method == 'POST':
        form = ModuleForm(request.POST)
        if form.is_valid():
            module = form.save(commit=False)
            module.course = course
            module.save()
            messages.success(request, 'Module added successfully!')
            return redirect('instructor_dashboard')
    else:
        form = ModuleForm()

    return render(request, 'module_create.html', {'form': form, 'course': course})

@login_required
def create_lesson(request, course_id):
    # Ensure the instructor owns this course
    course = get_object_or_404(Course, id=course_id, instructor=request.user)

    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, user=request.user, course=course)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course  # your Lesson model has a course field
            lesson.save()
            messages.success(request, "Lesson added successfully!")
            return redirect('instructor_dashboard')
        else:
            print(form.errors)  # for debugging
    else:
        form = LessonForm(user=request.user, course=course)

    return render(request, 'lesson_create.html', {'form': form, 'course': course})


def generate_signature(total_amount, transaction_uuid, product_code, secret_key):
    """
    Build the signature string exactly as eSewa expects:
    "total_amount=<total>,transaction_uuid=<uuid>,product_code=<code>"
    Then HMAC-SHA256 + base64
    """
    # ensure consistent formatting (use same types, no extra spaces)
    message = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
    digest = hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(digest).decode('utf-8')

@login_required
def checkout(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    service_charge = Decimal('50.00')
    total_amount = (Decimal(course.price) + service_charge).quantize(Decimal('0.01'))

    context = {
        'course': course,
        'service_charge': service_charge,
        'total_amount': total_amount,
    }
    return render(request, 'checkout.html', context)

# @login_required
# def process_payment(request):
#     if request.method != "POST":
#         return redirect('checkout', course_id=request.POST.get('course_id') or "")

#     user = request.user
#     full_name = request.POST.get("name")
#     email = request.POST.get("email")
#     phone = request.POST.get("phone")
#     address = request.POST.get("address")
#     city = request.POST.get("city")
#     country = request.POST.get("country", "Nepal")
#     course_id = request.POST.get("course_id")
#     amount = Decimal(request.POST.get("amount") or '0.00')
#     service_charge = Decimal('50.00')
#     total_amount = (amount + service_charge).quantize(Decimal('0.01'))
#     payment_type = request.POST.get("payment_type")

#     # Get the Course object (required for ForeignKey)
#     course = get_object_or_404(Course, id=course_id)

#     transaction_uuid = str(uuid.uuid4())
#     order = Order.objects.create(
#         user=user,
#         full_name=full_name,
#         email=email,
#         phone=phone,
#         address=address,
#         city=city,
#         country=country,
#         course=course,             # Pass the Course instance
#         amount=total_amount,
#         payment_type=payment_type,
#         transaction_uuid=transaction_uuid,
#         status="Pending",
#     )

#     # COD: show success page (or order confirmation)
#     if payment_type == "cod":
#         order.status = "Pending"  # or "COD Pending"
#         order.save()
#         return render(request, 'esewa_success.html', {'order': order})

#     # eSewa: prepare signature and redirect form template
#     if payment_type == "esewa":
#         product_code = getattr(settings, "ESEWA_PRODUCT_CODE", "EPAYTEST")
#         secret_key = getattr(settings, "ESEWA_SECRET_KEY", "")
#         signature = generate_signature(total_amount, transaction_uuid, product_code, secret_key)
#         success_url = request.build_absolute_uri(reverse('payment_success')) + "?"
#         failure_url = request.build_absolute_uri(reverse('payment_fail')) + "?"

#         context = {
#             'order': order,
#             'amount': amount,               # original product amount (optional)
#             'total_amount': total_amount,   # must be used in form and signature
#             'transaction_uuid': transaction_uuid,
#             'product_code': product_code,
#             'signature': signature,
#             'success_url': success_url,
#             'failure_url': failure_url,
#         }
#         return render(request, 'esewa_payment.html', context)

#     # fallback
#     return redirect('checkout', course_id=course_id)

@login_required
def process_payment(request):
    if request.method != "POST":
        return redirect('checkout', course_id=request.POST.get('course_id') or "")

    user = request.user
    full_name = request.POST.get("name")
    email = request.POST.get("email")
    phone = request.POST.get("phone")
    address = request.POST.get("address")
    city = request.POST.get("city")
    country = request.POST.get("country", "Nepal")
    course_id = request.POST.get("course_id")
    amount = Decimal(request.POST.get("amount") or '0.00')
    service_charge = Decimal('50.00')
    total_amount = (amount + service_charge).quantize(Decimal('0.01'))
    payment_type = request.POST.get("payment_type")

    # Get the Course object
    course = get_object_or_404(Course, id=course_id)

    transaction_uuid = str(uuid.uuid4())
    order = Order.objects.create(
        user=user,
        full_name=full_name,
        email=email,
        phone=phone,
        address=address,
        city=city,
        country=country,
        course=course,
        amount=total_amount,
        payment_type=payment_type,
        transaction_uuid=transaction_uuid,
        status="Pending",
    )

    # Save order id in session for success page
    request.session["current_order_id"] = order.id

    if payment_type == "cod":
        order.status = "Pending"
        order.save()
        return render(request, 'esewa_success.html', {'order': order})

    if payment_type == "esewa":
        product_code = getattr(settings, "ESEWA_PRODUCT_CODE", "EPAYTEST")
        secret_key = getattr(settings, "ESEWA_SECRET_KEY", "")
        signature = generate_signature(total_amount, transaction_uuid, product_code, secret_key)

        # session-based success URL
        success_url = request.build_absolute_uri(reverse('payment_success'))
        failure_url = request.build_absolute_uri(reverse('payment_fail'))

        context = {
            'order': order,
            'total_amount': total_amount,
            'transaction_uuid': transaction_uuid,
            'product_code': product_code,
            'signature': signature,
            'success_url': success_url,
            'failure_url': failure_url,
        }
        return render(request, 'esewa_payment.html', context)

    return redirect('checkout', course_id=course_id)

# @login_required
# def payment_success(request):
#     # eSewa returns:
#     # ?oid=transaction_uuid & amt=amount & refId=reference_id
#     oid = request.GET.get("oid")
#     amt = request.GET.get("amt")
#     ref_id = request.GET.get("product_code")

#     # Basic validation
#     if not oid:
#         return render(request, "esewa_failed.html", {"message": "Invalid payment data."})

#     try:
#         order = Order.objects.get(transaction_uuid=oid, user=request.user)
#     except Order.DoesNotExist:
#         return render(request, "esewa_failed.html", {"message": "Order not found."})

#     verify_url = "https://rc-epay.esewa.com.np/api/epay/transaction/status/"
#     payload = {
#         "product_code": "EPAYTEST",   # Your real code in production (eSewa प्रदान गर्ने)
#         "total_amount": str(order.amount),
#         "transaction_uuid": oid,
#     }

#     try:
#         response = requests.post(verify_url, json=payload)
#         data = response.json()
#     except:
#         return render(request, "esewa_failed.html", {"message": "eSewa verification failed."})

#     if data.get("status") != "COMPLETE":
#         return render(request, "esewa_failed", {"message": "Payment not verified with eSewa."})

#     order.status = "Success"
#     order.transaction_ref_id = ref_id
#     order.save()

#     enrollment, created = Enrollment.objects.get_or_create(
#         student=request.user,
#         course=order.course
#     )
    
#     return redirect("payment_content", course_id=order.course.id)

@login_required
def payment_success(request):
    order_id = request.session.get("current_order_id")
    if not order_id:
        return render(request, "esewa_failed.html", {"message": "Order info missing."})

    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return render(request, "esewa_failed.html", {"message": "Order not found."})

    # Optionally verify with eSewa API here if needed
    order.status = "Completed"  # mark as success
    order.transaction_ref_id = request.GET.get("refId", "")  # refId optional in session method
    order.save()

    # Create Enrollment
    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user,
        course=order.course
    )

    # Clear session
    if "current_order_id" in request.session:
        del request.session["current_order_id"]

    return redirect("enrolled_course", course_id=order.course.id)

# @receiver(post_save, sender=Order)
# def create_enrollment_on_success(sender, instance, created, **kwargs):
#     """Automatically create enrollment when order status becomes Success"""
#     if instance.status == "Success" and instance.course:
#         try:
#             Enrollment.objects.update_or_create(
#                 student=instance.user,
#                 course=instance.course,
#                 defaults={
#                     'progress': 0,
#                     'completed_at': None,
#                 }
#             )
#             print(f"Auto-enrollment created for order {instance.id}")
#         except Exception as e:
#             print(f"Auto-enrollment failed: {e}")

@login_required
def payment_fail(request):
    transaction_uuid = request.GET.get('transaction_uuid') or request.POST.get('transaction_uuid')
    order = Order.objects.filter(transaction_uuid=transaction_uuid).first()
    if order:
        order.status = "Failed"
        order.save()
    return render(request, 'esewa_failed.html', {'order': order})

@login_required
def payment_history(request):
    pass

# @login_required
# def download_invoice(request, payment_id):
#     payment = Payment.objects.get(id=payment_id, student=request.user)
#     pdf_buffer = generate_invoice(payment)
#     return FileResponse(pdf_buffer, as_attachment=True, filename=f"Invoice_{payment.transaction_uuid}.pdf")

# @login_required
# def export_payments_csv(request):
#     payments = Payment.objects.filter(student=request.user)

#     import csv
#     from django.http import HttpResponse

#     response = HttpResponse(content_type='text/csv')
#     response['Content-Disposition'] = 'attachment; filename="payment_history.csv"'
#     writer = csv.writer(response)
#     writer.writerow(["Course", "Amount", "Transaction ID", "Status", "Date"])
#     for p in payments:
#         writer.writerow([p.course.title, p.amount, p.transaction_uuid, p.status, p.created_at])
#     return response

# @login_required
# def export_payments_pdf(request):
#     payments = Payment.objects.filter(student=request.user)

#     response = HttpResponse(content_type='application/pdf')
#     response['Content-Disposition'] = 'attachment; filename="payment_history.pdf"'

#     p = canvas.Canvas(response, pagesize=letter)
#     width, height = letter
#     y = height - 50
#     p.setFont("Helvetica-Bold", 16)
#     p.drawString(50, y, "Payment History Report")
#     y -= 40
#     p.setFont("Helvetica", 12)
#     for payment in payments:
#         text = f"{payment.created_at} | {payment.course.title} | Rs. {payment.amount} | {payment.status}"
#         p.drawString(50, y, text)
#         y -= 20
#     p.save()
#     return response

def some_error_page(request):
    return render(request, "error1.html")

@login_required
def enrolled_course(request):
    # Fetch all enrollments of the student
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course', 'course__instructor')

    # Attach progress for each course
    for enrollment in enrollments:
        lessons = enrollment.course.modules.prefetch_related('module_lessons')
        total_lessons = sum(module.module_lessons.count() for module in lessons)
        completed_lessons = 0
        for module in lessons:
            for lesson in module.module_lessons.all():
                progress = LessonProgress.objects.filter(student=request.user, lesson=lesson).first()
                if progress and progress.status == "Completed":
                    completed_lessons += 1
        enrollment.progress = round((completed_lessons / total_lessons) * 100, 1) if total_lessons > 0 else 0

    context = {
        'enrollments': enrollments
    }
    return render(request, 'enrolled_course.html', context)

@login_required
def student_profile(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)  # ensure profile exists

    enrolled_courses = Enrollment.objects.filter(student=user).select_related('course')

    context = {
        'user': user,
        'profile': profile,
        'enrolled_courses': enrolled_courses,
    }
    return render(request, 'student_profile.html', context)

@login_required
def update_student_profile(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)  # ensure profile exists

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = UserProfileUpdateForm(request.POST, request.FILES, instance=profile)
        password_form = PasswordUpdateForm(request.POST)

        # Validate forms
        if user_form.is_valid() and profile_form.is_valid() and password_form.is_valid():

            # 1Update user fields if filled
            user_data = user_form.cleaned_data
            if user_data.get('first_name'):
                user.first_name = user_data['first_name']
            if user_data.get('last_name'):
                user.last_name = user_data['last_name']
            if user_data.get('email'):
                user.email = user_data['email']
            user.save()

            #  Update profile image if uploaded
            if request.FILES.get('image'):
                profile.image = request.FILES['image']
                profile.save()

            # Update password if fields filled
            current_password = password_form.cleaned_data.get('current_password')
            new_password = password_form.cleaned_data.get('new_password')
            confirm_password = password_form.cleaned_data.get('confirm_password')

            if current_password or new_password or confirm_password:
                # All three fields must be filled
                if not (current_password and new_password and confirm_password):
                    messages.error(request, "Please fill all password fields to change password.")
                    return redirect('update_student_profile')

                # Check current password
                if not user.check_password(current_password):
                    messages.error(request, "Current password is incorrect.")
                    return redirect('update_student_profile')

                # Check new password confirmation
                if new_password != confirm_password:
                    messages.error(request, "New passwords do not match.")
                    return redirect('update_student_profile')

                # Set new password
                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)  # Keep user logged in
                messages.success(request, "Password updated successfully!")

            messages.success(request, "Profile updated successfully!")
            return redirect('student_profile')

        else:
            messages.error(request, "Please correct the errors below.")

    else:
        user_form = UserUpdateForm(instance=user)
        profile_form = UserProfileUpdateForm(instance=profile)
        password_form = PasswordUpdateForm()

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
    }
    return render(request, 'update_student_profile.html', context)

def change_student_password(request):
    pass

@login_required
def pending_assignments(request):
    # Get all courses the student is enrolled in
    enrolled_courses = Enrollment.objects.filter(student=request.user).values_list('course_id', flat=True)

    # Get assignments for those courses
    assignments = Assignment.objects.filter(course_id__in=enrolled_courses)

    # Exclude assignments the student has already submitted
    submitted_assignments = Submission.objects.filter(student=request.user).values_list('assignment_id', flat=True)
    pending_assignments = assignments.exclude(id__in=submitted_assignments)

    context = {
        'pending_assignments': pending_assignments
    }
    return render(request, 'pending_assignment.html', context)

@login_required
def completed_courses(request):
    """Show all courses where the student finished all lessons."""
    enrollments = Enrollment.objects.filter(student=request.user).select_related("course")

    completed = []
    for enroll in enrollments:
        total_lessons = sum(module.module_lessons.count() for module in enroll.course.modules.all())
        completed_lessons = LessonProgress.objects.filter(
            student=request.user, lesson__module__course=enroll.course, status="Completed"
        ).count()

        if total_lessons > 0 and total_lessons == completed_lessons:
            enroll.progress = 100
            completed.append(enroll)

    return render(request, "completed_courses.html", {"completed_courses": completed})

@login_required
def instructor_profile(request):
    return render(request, 'instructor_profile.html')

def update_instructor_profile(request):
    user = request.user
    profile = user.userprofile  # Or user.instructorprofile if you created one

    if request.method == "POST":
        user_form = InstructorUserForm(request.POST, instance=user)
        profile_form = InstructorProfileForm(request.POST, request.FILES, instance=profile)
        password_form = InstructorPasswordForm(user, request.POST)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()

            # Handle password update
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, user)

            messages.success(request, "Profile updated successfully!")
            return redirect('instructor_profile')
        else:
            messages.error(request, "Please correct the errors below.")

    else:
        user_form = InstructorUserForm(instance=user)
        profile_form = InstructorProfileForm(instance=profile)
        password_form = InstructorPasswordForm(user)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
        'instructor': user,  # for image preview in template
    }
    return render(request, 'update_instructor_profile.html', context)

def change_instructor_password(request):
    pass

def about(request):
    return render(request, 'about.html')

@login_required
def view_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    student = request.user

    # Check if student already submitted
    submission = Submission.objects.filter(assignment=assignment, student=student).first()
    submission_exists = submission is not None

    questions = assignment.questions.all()  # Assuming Assignment has a related_name="questions"

    if request.method == "POST" and not submission_exists:

        # Create the Submission object first
        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content="",   # optional summary, can fill later
            status="pending"  # or "submitted"
        )

        # Store each answer in StudentAnswer table
        for question in questions:
            answer_text = request.POST.get(f"answer_{question.id}", "").strip()
            if answer_text:
                StudentAnswer.objects.create(
                    question=question,
                    submission=submission.student,  # link to the student user
                    answer_text=answer_text
                )
        
        instructor = assignment.created_by

        if instructor and instructor.email:
            subject = "New Assignment Submission Received"
            message = (
                f"Hello {instructor.first_name or instructor.username},\n\n"
                f"The student {student.get_full_name() or student.username} "
                f"has submitted the assignment: \"{assignment.title}\".\n\n"
                "You can review their answers in your instructor dashboard.\n\n"
                "View the submitted answer and give the instructions feedback.\n\n"
                "Best regards,\n"
                "Your Student"
            )

            send_mail(
                subject,
                message,
                "student@example.com",
                [instructor.email],
                fail_silently=True
            )

        messages.success(request, "Assignment submitted successfully!")
        return redirect('pending_assignments')

    context = {
        'assignment': assignment,
        'questions': questions,
        'submission_exists': submission_exists,
        'submission': submission,
    }
    return render(request, 'view_assignment.html', context)

@login_required
def instructor_submissions_list(request):
    instructor = request.user

    # Instructor को सबै assignments
    assignments = Assignment.objects.filter(created_by=instructor)

    # ती assignments का सबै submissions
    submissions = Submission.objects.filter(assignment__in=assignments).select_related('student', 'assignment')

    return render(request, 'submitted_answers_list.html', {
        'submissions': submissions
    })

@login_required
def instructor_submission_detail(request, submission_id):
    submission = get_object_or_404(
        Submission,
        id=submission_id,
        assignment__created_by=request.user   # Instructor only sees their own submissions
    )

    # All answers for this submission
    answers = StudentAnswer.objects.filter(submission=submission.student).select_related('question')

    # Handle marks & feedback post
    if request.method == "POST":
        grade = request.POST.get("marks")
        feedback = request.POST.get("feedback")

        submission.grade = grade
        submission.feedback = feedback
        submission.status = "graded"
        submission.save()

        subject = "Your Assignment Has Been Graded"
        message = (
            f"Hello {submission.student.get_full_name() or submission.student.username},\n\n"
            f"Your assignment '{submission.assignment.title}' has been graded by your instructor.\n\n"
            f"Marks Obtained: {grade}\n"
            f"Feedback: {feedback}\n\n"
            "Best regards,\n"
            "Your Instructor"
        )
        student_email = submission.student.email   # ✔ This is a string email

        if student_email:
            send_mail(
                subject,
                message,
                "instructor@example.com",  # from
                [student_email],       # to
                fail_silently=False,
            )

        messages.success(request, "Marks & feedback saved successfully!")
        return redirect('instructor_submitted_answers')

    return render(request, 'submission_detail.html', {
        'submission': submission,
        'answers': answers
    })

@login_required
def sponsor_checkout(request, student_id):
    student = get_object_or_404(UserProfile, id=student_id, role='student')

    if request.method == "POST":
        amount = request.POST.get("amount")
        if not amount or float(amount) <= 0:
            messages.error(request, "Invalid amount.")
            return redirect('fund_student')

        # Pass data to checkout template
        return render(request, "sponsor_checkout.html", {
            "student": student,
            "amount": amount
        })

    # If accessed via GET, redirect back
    return redirect("fund_student")

# @login_required
# def sponsor_payment_process(request, student_id):
#     student = get_object_or_404(UserProfile, id=student_id, role='student')

#     if request.method == 'POST':
#         amount = request.POST.get('amount')
#         transaction_uuid = str(uuid.uuid4())
#         product_code = f"fund-{student.id}-{transaction_uuid}"
#         message = f"Funding for {student.user.get_full_name()}"
        
#         # Save temporary record
#         Funding.objects.create(
#             student=student,
#             sponsor=request.user,
#             amount=amount,
#             message=message,
#             transaction_uuid=transaction_uuid,
#             status='pending'
#         )

#         # Prepare data for signature (eSewa requires signed fields)
#         # Example simple signature (replace with real logic if eSewa SDK/API requires)
#         signed_fields = f"total_amount,transaction_uuid,product_code"
#         data_string = f"{amount},{transaction_uuid},{product_code}"
#         secret_key = settings.ESEWA_SECRET_KEY.encode()
#         signature = base64.b64encode(hmac.new(secret_key, data_string.encode(), hashlib.sha256).digest()).decode()

#         return render(request, 'sponsor_payment.html', {
#             'total_amount': amount,
#             'transaction_uuid': transaction_uuid,
#             'product_code': product_code,
#             'signature': signature,
#             'success_url': request.build_absolute_uri('/esewa/success/'),
#             'failure_url': request.build_absolute_uri('/esewa/fail/')
#         })

#     return redirect('fund_student')

@login_required
def sponsor_payment_process(request, student_id):
    """
    Sponsor funding for a student via eSewa.
    Funding table stores minimal info.
    Order table stores payment details and transaction info.
    """

    # Fetch student
    student = get_object_or_404(UserProfile, id=student_id, role="student")

    if request.method == "POST":
        # Get amount from form
        amount = request.POST.get("amount")
        if not amount or float(amount) <= 0:
            messages.error(request, "Enter a valid funding amount.")
            return redirect(request.path)

        # 1️⃣ Save minimal Funding record
        funding = Funding.objects.create(
            student=student,
            sponsor=request.user,
            amount=amount,
            message=f"Funding by {request.user.username} for {student.user.get_full_name()}"
        )

        # 2️⃣ Create Order record
        transaction_uuid = str(uuid.uuid4())
        order = Order.objects.create(
            user=request.user,
            amount=amount,
            full_name=request.POST.get("name", request.user.get_full_name()),
            email=request.POST.get("email", request.user.email),
            phone=request.POST.get("phone", ""),
            address=request.POST.get("address", ""),
            city=request.POST.get("city", ""),
            country="Nepal",
            payment_type="esewa",
            status="Pending",
            transaction_uuid=transaction_uuid
        )

        # Link Funding → Order
        funding.order = order
        funding.save()

        # 3️⃣ Prepare eSewa signature
        product_code = settings.ESEWA_PRODUCT_CODE
        total_amount = str(amount)
        signed_fields = "total_amount,transaction_uuid,product_code"

        data_string = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
        signature = base64.b64encode(
            hmac.new(settings.ESEWA_SECRET_KEY.encode(), data_string.encode(), hashlib.sha256).digest()
        ).decode()

        # 4️⃣ Dynamic URLs for redirect
        success_url = request.build_absolute_uri(reverse('sponsor_payment_success'))
        failure_url = request.build_absolute_uri(reverse('sponsor_payment_fail'))

        # 5️⃣ Render eSewa redirect page
        return render(request, "sponsor_payment.html", {
            "total_amount": total_amount,
            "transaction_uuid": transaction_uuid,
            "product_code": product_code,
            "signature": signature,
            "signed_field_names": signed_fields,
            "success_url": success_url,
            "failure_url": failure_url,
            "student": student,
            "amount": total_amount
        })

    # If GET request → redirect to fund_student
    return redirect("fund_student")

@login_required
def sponsor_payment_success(request):
    """
    Called by eSewa after successful payment.
    Marks order as completed and updates funding.
    If verification fails, still redirect to dashboard with message.
    """
    encoded_data = request.GET.get("data")
    if not encoded_data:
        messages.success(request, "Payment successful!")
        return redirect("sponsor_dashboard")

    try:
        decoded_json = base64.b64decode(encoded_data).decode()
        data = json.loads(decoded_json)
        transaction_uuid = data.get("transaction_uuid")
        total_amount = data.get("total_amount")
        product_code = data.get("product_code")
        signature = data.get("signature")
    except Exception:
        messages.success(request, "Payment successful!")
        return redirect("sponsor_dashboard")

    # Verify signature
    try:
        raw_string = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
        generated_signature = base64.b64encode(
            hmac.new(settings.ESEWA_SECRET_KEY.encode(), raw_string.encode(), hashlib.sha256).digest()
        ).decode()
    except Exception:
        messages.success(request, "Payment successful!")
        return redirect("sponsor_dashboard")

    if generated_signature != signature:
        messages.success(request, "Payment successful!")
        return redirect("sponsor_dashboard")

    # Update order
    order = Order.objects.filter(transaction_uuid=transaction_uuid).first()
    if order:
        order.status = "Completed"
        order.save()

        # Update funding
        funding = Funding.objects.filter(order=order).first()
        if funding:
            funding.status = "success"
            funding.save()

            student = funding.student
            sponsor = funding.sponsor
            amount = funding.amount

            if student and student.email:
                subject = "You have received sponsorship Funding!"
                message = (
                    f"Hello {student.user.get_full_name() or student.user.username},\n\n"
                    f"You have received a sponsorship funding of Rs. {amount} from {sponsor.get_full_name() or sponsor.username}.\n\n"
                    f"Funded Amount: Rs. {amount}\n"
                    f"Purpose: {funding.message}\n\n"
                    "Best regards,\n"
                    "Enhaced LMS Team"
                )
                send_mail(
                    subject,
                    message,
                    "sponsor@example.com",
                    [student.user.email],
                    fail_silently=False,
                )

    messages.success(request, "Payment successful!")
    return redirect("sponsor_dashboard")

@login_required
def sponsor_payment_fail(request):

    """
    Called by eSewa after failed payment.
    """
    messages.error(request, "Payment failed. Please try again.")
    return redirect("sponsor_dashboard")
