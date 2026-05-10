from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Q, Count, Avg, Min
from django.utils import timezone
from urllib3 import request
from .models import *
from .forms import *
from .utils import *    
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, logout, authenticate
from django.db.models import Sum
import uuid
from django.core.paginator import Paginator
from decimal import Decimal
import uuid
import hmac
import hashlib
import base64
from django.db import transaction
import json
from django.conf import settings
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.dispatch import receiver
from django.contrib.auth import update_session_auth_hash
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import pandas as pd

def signup(request):
    if request.method == "POST":
        fullname = request.POST.get("fullname")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        role = request.POST.get("role")
        image = request.FILES.get("profile_image")

        if password != confirm_password:
            messages.error(request, "Password do not match!")
            return redirect('signup')

        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters Long!")
            return redirect('signup')
        
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Invalid email address!")
            return redirect('signup')

        if User.objects.filter(username=email).exists():
            messages.error(request, "Email already exists!")
            return redirect('signup')
        
        if role not in ['student', 'instructor', 'sponsor']:
            messages.error(request, "Please select a valid role.")
            return redirect('signup')

        if image:
            valid_extensions = ['.jpg', '.jpeg', '.png']
            if not any(image.name.lower().endswith(ext) for ext in valid_extensions):
                messages.error(request, "Invalid image format! Only .jpg, .jpeg, .png allowed.")
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
        
        # Send welcome email
        subject = "Welcome to Our Platform 🎉"
        message = f"""
        Hi {fullname},

        Your account has been created successfully!

        You can now log in using your email: {email}

        Thank you for joining us.

        - Team
        """
        recipient_list = [email]

        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
        except Exception as e:
            messages.warning(request, "Account created, but email could not be sent.")

        messages.success(request, "Account created Successfully.")
        return redirect('signin')
            
    return render(request, 'signup.html')

def signin(request):
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
            role = user.profile.role
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
        courses = courses.filter(category__id=category) 
    if level:
        courses = courses.filter(level=level)
    if search:
        courses = courses.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(instructor__first_name__icontains=search) |
            Q(instructor__last_name__icontains=search) |
            Q(level__icontains=search)
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
        student__user = request.user,
    ).aggregate(total=Sum('amount'))['total'] or 0

    fundings = Funding.objects.filter(course=course, student__user = request.user)

    # Discounted price calculation
    discounted_price = float(course.price) - float(total_funded)
    if discounted_price < 0:
        discounted_price = 0

    if discounted_price == 0 and not enrolled:
        Enrollment.objects.get_or_create(student=request.user, course = course)
        return redirect('course_detail', course_id=course.id)
    
    # Handle enrollment POST request
    if request.method == 'POST' and not enrolled:
        Enrollment.objects.create(student=request.user, course=course)
        return redirect('course_detail', course_id=course.id)

    context = {
        'course': course,
        'modules': modules,
        'enrolled': enrolled,
        'total_funded': total_funded,          
        'discounted_price': discounted_price,  
        'fundings': fundings,
    }

    return render(request, 'course_detail.html', context)

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

@login_required
def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(
        Lesson.objects.select_related('module', 'module__course'),
        id=lesson_id
    )

    # Always use module → course (NOT lesson.course)
    course = lesson.module.course

    # Check enrollment
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        return redirect(f"/checkout/?course_id={course.id}")

    # Sidebar modules
    modules = course.modules.prefetch_related('module_lessons').all()

    # Mark lesson as "in_progress"
    progress, _ = LessonProgress.objects.get_or_create(
        student=request.user,
        lesson=lesson
    )
    if progress.status == "not_started":
        progress.status = "in_progress"
        progress.save()

    # FIXED: Get ALL lessons across modules (STRICT ORDER)
    all_lessons = list(
        Lesson.objects.filter(module__course_id=course.id)
        .select_related('module')
        .order_by('module__order', 'module__id', 'order', 'id')
    )

    # SAFE INDEX (no object mismatch bug)
    current_index = next(
        (i for i, l in enumerate(all_lessons) if l.id == lesson.id),
        None
    )

    # Navigation
    previous_lesson = (
        all_lessons[current_index - 1]
        if current_index is not None and current_index > 0
        else None
    )

    next_lesson = (
        all_lessons[current_index + 1]
        if current_index is not None and current_index < len(all_lessons) - 1
        else None
    )

    # Progress calculation
    lesson_progress_qs = LessonProgress.objects.filter(
        student=request.user,
        lesson__module__course=course
    )

    progress_map = {p.lesson.id: p.status for p in lesson_progress_qs}

    total_lessons = len(all_lessons)
    completed_lessons = lesson_progress_qs.filter(status="completed").count()

    progress_percent = int((completed_lessons / total_lessons) * 100) if total_lessons else 0

    # Update Enrollment progress
    Enrollment.objects.filter(
        student=request.user,
        course=course
    ).update(progress=progress_percent)

    # Update StudentProgress
    StudentProgress.objects.update_or_create(
        student=request.user,
        course=course,
        defaults={"progress": progress_percent}
    )

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
def complete_course(request, course_id):
    if request.method != "POST":
        return redirect("student_dashboard")

    course = get_object_or_404(Course, id=course_id)

    lessons = Lesson.objects.filter(module__course=course)

    # UPDATE LESSON PROGRESS (MISSING PART)
    LessonProgress.objects.filter(
        student=request.user,
        lesson__module__course=course
    ).update(status="completed")

    # Enrollment
    enrollment, _ = Enrollment.objects.get_or_create(
        student=request.user,
        course=course
    )

    enrollment.completed = True
    enrollment.completed_at = timezone.now()
    enrollment.progress = 100
    enrollment.save()

    # StudentProgress
    StudentProgress.objects.update_or_create(
        student=request.user,
        course=course,
        defaults={"progress": 100}
    )

    return redirect("student_dashboard")

@login_required
def assignment_delete(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    if request.user == assignment.created_by:  # ensure only creator can delete
        assignment.delete()
        messages.success(request, "Assignment deleted successfully.")
    else:
        messages.error(request, "You do not have permission to delete this assignment.")
    return redirect('instructor_dashboard')

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

    today = timezone.now().date()
    assignments = assignments.filter(due_date__gte=today)

    # 3. Get student submissions
    submitted_assignments = Submission.objects.filter(
        student=user
    ).values_list('assignment_id', flat=True)

    # 4. Pending assignments (same as your working page)
    pending_assignments = assignments.exclude(id__in=submitted_assignments)

    # 5. Count
    pending_assignments_count = pending_assignments.count()

    # Total money spent (only completed orders)
    total_money_spent = Order.objects.filter(
        user = user,
        status = "Completed"
    ).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'enrollments': enrollments,
        'enrolled_courses_count': enrolled_courses_count,
        'completed_courses_count': completed_courses_count,
        'pending_assignments_count': pending_assignments_count,
        'pending_assignments': pending_assignments,
        'total_money_spent': total_money_spent,
    }
    return render(request, 'student_dashboard.html', context)

@login_required
def instructor_dashboard(request):
    user = request.user
    courses = Course.objects.filter(instructor=user)
    total_courses = courses.count()
    total_students = Enrollment.objects.filter(course__in=courses).values('student').distinct().count()
    total_assignments = sum(course.assignments.count() for course in courses)

    total_revenue = get_total_revenue(courses)

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
        'total_revenue': total_revenue,
    }
    return render(request, 'instructor_dashboard.html', context)

def sponsor_dashboard(request):
    sponsor = request.user

    # Get filters
    search = request.GET.get("search")
    progress_filter = request.GET.get("progress")
    status_filter = request.GET.get("status")

    sponsored_students = UserProfile.objects.filter(
        fundings__sponsor=sponsor,
        role="student"
    ).annotate(
        amount_sponsored=Sum("fundings__amount"),
        first_sponsored_date=Min("fundings__funded_at"),
        enrolled_courses=Count("user__enrollments", distinct=True),
        avg_progress=Avg("user__enrollments__progress"),
    )

    # Search (student name)
    if search:
        sponsored_students = sponsored_students.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )

    # Progress Filter
    if progress_filter == "low":
        sponsored_students = sponsored_students.filter(avg_progress__lt=30)
    elif progress_filter == "medium":
        sponsored_students = sponsored_students.filter(avg_progress__gte=30, avg_progress__lt=70)
    elif progress_filter == "high":
        sponsored_students = sponsored_students.filter(avg_progress__gte=70)

    # Status Filter
    if status_filter == "completed":
        sponsored_students = sponsored_students.filter(avg_progress=100)
    elif status_filter == "ongoing":
        sponsored_students = sponsored_students.filter(avg_progress__lt=100)

    sponsored_students = sponsored_students.distinct()

    # Total funds
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
        "remaining_balance": 0,
        "ongoing_sponsorships": sponsored_students.count(),
        "fundings": fundings,
        "search_query": search,
        "selected_progress": progress_filter,
        "selected_status": status_filter,
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
def update_sponsor_profile(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        user_form = SponsorUserForm(request.POST, instance=user)
        profile_form = SponsorProfileForm(request.POST, request.FILES, instance=profile)
        password_form = PasswordUpdateForm(request.POST)

        if user_form.is_valid() and profile_form.is_valid() and password_form.is_valid():

            # Save user directly (clean way)
            user_form.save()

            # Save profile (image + other fields)
            profile_form.save()

            # Password update logic
            current_password = password_form.cleaned_data.get('current_password')
            new_password = password_form.cleaned_data.get('new_password')
            confirm_password = password_form.cleaned_data.get('confirm_password')

            if current_password or new_password or confirm_password:

                if not (current_password and new_password and confirm_password):
                    messages.error(request, "Please fill all password fields.")
                    return redirect('update_sponsor_profile')

                if not user.check_password(current_password):
                    messages.error(request, "Current password is incorrect.")
                    return redirect('update_sponsor_profile')

                if new_password != confirm_password:
                    messages.error(request, "Passwords do not match.")
                    return redirect('update_sponsor_profile')

                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)

                messages.success(request, "Password updated successfully!")

            messages.success(request, "Sponsor profile updated successfully!")
            return redirect('sponsor_profile')

        else:
            messages.error(request, "Please fix the errors.")

    else:
        user_form = SponsorUserForm(instance=user)
        profile_form = SponsorProfileForm(instance=profile)
        password_form = PasswordUpdateForm()

    return render(request, 'update_sponsor_profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
    })

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

@login_required
def course_profile_view(request, course_id):

    course = get_object_or_404(Course, id=course_id)

    # Enrollment
    enrollments = Enrollment.objects.filter(course=course)
    total_students = enrollments.count()
    completed_students = enrollments.filter(completed=True).count()
    avg_progress = enrollments.aggregate(avg=Avg("progress"))['avg'] or 0

    # Funding
    fundings = Funding.objects.filter(course=course)
    total_funding = fundings.aggregate(total=Sum("amount"))['total'] or 0

    sponsor_list = fundings.values(
        "sponsor__username"
    ).annotate(
        total_amount=Sum("amount")
    ).order_by("-total_amount")

    context = {
        "course": course,
        "total_students": total_students,
        "completed_students": completed_students,
        "avg_progress": round(avg_progress, 2),
        "total_funding": total_funding,
        "sponsor_list": sponsor_list,
        "fundings": fundings,
        "enrollments": enrollments,
    }

    return render(request, "course_profile_view.html", context)

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
    courses = Course.objects.all()
    # Ensure only sponsors can access this page
    try:
        user_profile = request.user.profile
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
        'courses': courses,
        'sponsor_name': user_profile.user.first_name or user_profile.user.username,  
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
        course = request.POST.get('course')

        Sponsorship.objects.create(
            sponsor=sponsor,
            student=student,
            course=course,
            funded_amount=amount
        )

        if student.email:
            send_mail(
                subject="🎉 You received sponsorship!",
                message=f"""
                        Hello {student.first_name or student.username},

                        Congratulations! 🎉

                        You have received sponsorship from {user.first_name or user.username}.

                        📚 Course: {course.title}
                        💰 Amount: NPR {amount}

                        Keep learning and growing 🚀

                        Best regards,
                        LMS Team
                        """,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[student.email],
                fail_silently=False,
            )

        messages.success(request, f"You have successfully funded {student.first_name or student.username}")
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

        # 1. Create Funding entry
        funding = Funding.objects.create(
            sponsor=sponsor,
            course=course,
            amount=amount,
            status="Pending",
            funded_at=timezone.now()
        )

        # 2. Create Order entry
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

        # 3. eSewa Signature Logic
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

        # 4. Success / Failure URLs
        success_url = request.build_absolute_uri(
            reverse("fund_course_esewa_success", args=[order.id])
        )
        failure_url = request.build_absolute_uri(
            reverse("fund_course_esewa_fail", args=[order.id])
        )

        # 5. Render Auto-submit Form
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


@login_required
def checkout(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    # Only course price (convert to paisa)
    course_price_paisa = int(float(course.price) * 100)

    total_amount_paisa = course_price_paisa

    context = {
        'course': course,
        'total_amount': "{:.2f}".format(total_amount_paisa / 100), 
        'total_amount_paisa': total_amount_paisa, 
    }

    return render(request, 'checkout.html', context)

@login_required
def process_payment(request):
    if request.method != "POST":
        return redirect("checkout")

    user = request.user

    course_id = request.POST.get("course_id")
    course = get_object_or_404(Course, id=course_id)

    payment_type = request.POST.get("payment_type")
    transaction_uuid = str(uuid.uuid4())

    # Get available sponsorship (correct way)
    fundings = Funding.objects.filter(course=course, status="Completed")

    available_funding = sum(
        (f.amount - f.used_amount) for f in fundings
    )

    course_price = Decimal(str(course.price))

    # Calculate sponsor_used and final_price
    sponsor_used = min(course_price, available_funding)
    final_price = course_price - sponsor_used

    # Safety
    if final_price < 0:
        final_price = Decimal("0.00")

    print("COURSE PRICE:", course_price)
    print("AVAILABLE FUNDING:", available_funding)
    print("SPONSOR USED:", sponsor_used)
    print("FINAL PRICE:", final_price)

    # If fully funded
    if final_price == 0:
        order = Order.objects.create(
            user=user,
            course=course,
            amount=0,
            sponsor_used=sponsor_used,  
            payment_type="Sponsored",
            transaction_uuid=transaction_uuid,
            status="Completed"
        )

        # deduct funding immediately
        apply_funding(course, sponsor_used)

        Enrollment.objects.get_or_create(
            student=user,
            course=course
        )

        return redirect("enrolled_course", course_id=course.id)

    # Create order with sponsor_used
    order = Order.objects.create(
        user=user,
        full_name=request.POST.get("name"),
        email=request.POST.get("email"),
        phone=request.POST.get("phone"),
        address=request.POST.get("address"),
        city=request.POST.get("city"),
        country="Nepal",
        course=course,
        amount=final_price,
        sponsor_used=sponsor_used,   
        payment_type=payment_type,
        transaction_uuid=transaction_uuid,
        status="Pending",
    )

    total_amount = format(final_price, ".2f")

    # COD
    if payment_type == "cod":
        Enrollment.objects.get_or_create(
            student=user,
            course=course
        )
        return redirect("enrolled_course", course_id=course.id)

    # eSewa
    if payment_type == "esewa":
        product_code = settings.ESEWA_PRODUCT_CODE
        secret_key = settings.ESEWA_SECRET_KEY

        signature = generate_signature(
            total_amount,
            transaction_uuid,
            product_code,
            secret_key
        )

        success_url = request.build_absolute_uri(reverse("payment_success"))
        failure_url = request.build_absolute_uri(reverse("payment_fail"))

        return render(request, "esewa_payment.html", {
            "total_amount": total_amount,
            "transaction_uuid": transaction_uuid,
            "product_code": product_code,
            "signature": signature,
            "success_url": success_url,
            "failure_url": failure_url,
        })

    return redirect("checkout")

@login_required
def payment_success(request):
    encoded_data = request.GET.get("data")

    if not encoded_data:
        return render(request, "esewa_failed.html", {
            "message": "No payment data received."
        })

    try:
        decoded_data = base64.b64decode(encoded_data).decode("utf-8")
        payment_data = json.loads(decoded_data)

        print("PAYMENT DATA:", payment_data)

        transaction_uuid = payment_data.get("transaction_uuid")
        status = payment_data.get("status", "").upper()

        if not transaction_uuid:
            return render(request, "esewa_failed.html", {
                "message": "Transaction ID missing."
            })

        order = Order.objects.get(
            transaction_uuid=transaction_uuid,
            user=request.user
        )

        # prevent duplicate processing
        if order.status == "Completed":
            return redirect("course_learn", course_id=order.course.id)

        if status in ["COMPLETE", "SUCCESS"]:
            with transaction.atomic():
                order.status = "Completed"
                order.save()

                course = order.course

                if order.sponsor_used > 0:
                    apply_funding(order.course, order.sponsor_used)

                    # UPDATE FUNDING STATUS
                    fundings = Funding.objects.filter(course=course, status="Completed")

                    for f in fundings:
                        if f.amount == f.used_amount:
                            f.status = "Sponsored"
                            f.save()

                Enrollment.objects.get_or_create(
                    student=request.user,
                    course=course
                )

            return redirect("course_learn", course_id=order.course.id)

        else:
            order.status = "Failed"
            order.save()

            return render(request, "esewa_failed.html", {
                "message": f"Payment not completed. Status: {status}"
            })

    except Exception as e:
        print("ERROR:", e)
        return render(request, "esewa_failed.html", {
            "message": "Payment verification failed."
        })
    
def payment_fail(request):
    order_id = request.GET.get("current_order_id")

    order = None
    if order_id:
        order = Order.objects.filter(id = order_id).first()
    
    if order:
        order.status = "Failed"
        order.save()
    
    return render(request, "esewa_failed.html", {"order": order})

@login_required
def payment_history(request):
    pass

def some_error_page(request):
    return render(request, "error1.html")

@login_required
def enrolled_course(request):
    # Fetch all enrollments of the student
    enrollments = Enrollment.objects.filter(student=request.user, completed=False).select_related('course', 'course__instructor')

    # Attach progress for each course
    for enrollment in enrollments:
        lessons = enrollment.course.modules.prefetch_related('module_lessons')
        total_lessons = sum(module.module_lessons.count() for module in lessons)
        completed_lessons = 0
        for module in lessons:
            for lesson in module.module_lessons.all():
                progress = LessonProgress.objects.filter(student=request.user, lesson=lesson).first()
                if progress and progress.status == "completed":
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
    profile, _ = UserProfile.objects.get_or_create(user=user)  

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = UserProfileUpdateForm(request.POST, request.FILES, instance=profile)
        password_form = PasswordUpdateForm(request.POST)

        # Validate forms
        if user_form.is_valid() and profile_form.is_valid() and password_form.is_valid():

            # Update user fields if filled
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

    today = timezone.now().date()
    assignments = assignments.filter(due_date__gte=today)

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
        total_lessons = Lesson.objects.filter(
            module__course=enroll.course
        ).count()
        completed_lessons = LessonProgress.objects.filter(
            student=request.user,
            lesson__module__course=enroll.course,
            status="completed"
        ).count()

        if total_lessons > 0 and total_lessons == completed_lessons:
            enroll.progress = 100
            completed.append(enroll)

    return render(request, "completed_courses.html", {"completed_courses": completed})

@login_required
def instructor_profile(request):
    instructor = request.user
    return render(request, 'instructor_profile.html', {'instructor': instructor})

def update_instructor_profile(request):
    user = request.user
    profile = user.profile 

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

    submission = Submission.objects.filter(
        assignment=assignment, student=student
    ).first()

    submission_exists = submission is not None
    questions = assignment.questions.all()

    if request.method == "POST" and not submission_exists:

        answers_to_save = []

        for question in questions:
            answer_text = request.POST.get(f"answer_{question.id}", "").strip()
            answer_file = request.FILES.get(f"file_{question.id}")
            selected_option = request.POST.get(f"answer_{question.id}")

            # Prevent blank answer per question
            if not answer_text and not answer_file and not selected_option:
                messages.error(
                    request,
                    f"Please answer Question {question.id}"
                )
                return redirect('view_assignment', assignment_id=assignment.id)

            answers_to_save.append({
                "question": question,
                "answer_text": answer_text or selected_option,
                "answer_file": answer_file
            })

        # Create submission AFTER validation
        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            file=answer_file if any(ans["answer_file"] for ans in answers_to_save) else None,
            content="Submitted answers",
            status="pending"
        )

        # Save answers
        for ans in answers_to_save:
            StudentAnswer.objects.create(
                submission=submission,
                question=ans["question"],
                answer_text=ans["answer_text"],
                answer_file=ans["answer_file"]
            )

        messages.success(request, "Assignment submitted successfully!")
        return redirect('pending_assignments')

    return render(request, 'view_assignment.html', {
        'assignment': assignment,
        'questions': questions,
        'submission_exists': submission_exists,
        'submission': submission,
    })

@login_required
def instructor_submissions_list(request):
    instructor = request.user

    assignments = Assignment.objects.filter(created_by=instructor)

    submissions = Submission.objects.filter(assignment__in=assignments).select_related('student', 'assignment')

    return render(request, 'submitted_answers_list.html', {
        'submissions': submissions
    })

@login_required
def instructor_submission_detail(request, submission_id):
    submission = get_object_or_404(
        Submission,
        id=submission_id,
        assignment__created_by=request.user  
    )

    # All answers for this submission
    answers = StudentAnswer.objects.filter(submission=submission).select_related('question')

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
                "instructor@example.com",  
                [student_email],       
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
        course_id = request.POST.get("course")

        if not course_id:
            messages.error(request, "Please select a course.")
            return redirect('fund_student')
        
        if not amount or float(amount) <= 0:
            messages.error(request, "Invalid amount.")
            return redirect('fund_student')

        # Pass data to checkout template
        return render(request, "sponsor_checkout.html", {
            "student": student,
            "amount": amount,
            "course_id": course_id
        })

    # If accessed via GET, redirect back
    return redirect("fund_student")

@login_required
def sponsor_payment_process(request, student_id):
    student = get_object_or_404(UserProfile, id=student_id, role="student")

    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount"))
        except:
            messages.error(request, "Invalid amount.")
            return redirect("fund_student")

        course_id = request.POST.get("course_id")

        if not course_id:
            messages.error(request, "Please select a course.")
            return redirect("fund_student")

        if amount <= 0:
            messages.error(request, "Enter a valid funding amount.")
            return redirect("fund_student")

        course = get_object_or_404(Course, id=course_id)

        # Create Order FIRST
        transaction_uuid = str(uuid.uuid4())

        order = Order.objects.create(
            user=request.user,
            course=course,
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

        # Create Funding linked to Order
        funding = Funding.objects.create(
            student=student,
            sponsor=request.user,
            course=course,
            amount=amount,
            message=f"Funding by {request.user.username} for {student.user.get_full_name()}",
            status="Pending"
        )

        funding.order = order
        funding.save()

        # eSewa signature
        product_code = settings.ESEWA_PRODUCT_CODE
        total_amount = str(amount)

        signed_fields = "total_amount,transaction_uuid,product_code"
        data_string = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"

        signature = base64.b64encode(
            hmac.new(settings.ESEWA_SECRET_KEY.encode(), data_string.encode(), hashlib.sha256).digest()
        ).decode()

        success_url = request.build_absolute_uri(reverse('sponsor_payment_success'))
        failure_url = request.build_absolute_uri(reverse('sponsor_payment_fail'))

        return render(request, "sponsor_payment.html", {
            "total_amount": total_amount,
            "transaction_uuid": transaction_uuid,
            "product_code": product_code,
            "signature": signature,
            "signed_field_names": signed_fields,
            "success_url": success_url,
            "failure_url": failure_url,
            "student": student,
            "course": course,
        })

    return redirect("fund_student")

@login_required
def sponsor_payment_success(request):
    encoded_data = request.GET.get("data")

    if not encoded_data:
        messages.error(request, "No payment data received.")
        return redirect("sponsor_dashboard")

    try:
        decoded_json = base64.b64decode(encoded_data).decode()
        data = json.loads(decoded_json)

        print("SPONSOR PAYMENT DATA:", data)

        transaction_uuid = data.get("transaction_uuid")
        signature = data.get("signature")
        signed_field_names = data.get("signed_field_names")

    except Exception as e:
        print("DECODE ERROR:", e)
        messages.error(request, "Payment verification failed.")
        return redirect("sponsor_dashboard")

    # CORRECT SIGNATURE VERIFICATION
    try:
        fields = signed_field_names.split(",")

        raw_list = []
        for field in fields:
            raw_list.append(f"{field}={data.get(field)}")

        raw_string = ",".join(raw_list)

        print("RAW STRING:", raw_string)

        generated_signature = base64.b64encode(
            hmac.new(settings.ESEWA_SECRET_KEY.encode(), raw_string.encode(), hashlib.sha256).digest()
        ).decode()

        print("GENERATED:", generated_signature)
        print("RECEIVED :", signature)

    except Exception as e:
        print("SIGNATURE ERROR:", e)
        messages.error(request, "Payment verification failed.")
        return redirect("sponsor_dashboard")

    # If signature fails → STOP
    if generated_signature != signature:
        print("SIGNATURE MISMATCH")
        messages.error(request, "Payment verification failed.")
        return redirect("sponsor_dashboard")

    # Update DB safely
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(
                transaction_uuid=transaction_uuid
            ).first()

            if not order:
                print("ORDER NOT FOUND")
                messages.error(request, "Order not found.")
                return redirect("sponsor_dashboard")

            # prevent duplicate
            if order.status == "Completed":
                return redirect("sponsor_dashboard")

            order.status = "Completed"
            order.save()

            funding = Funding.objects.select_for_update().filter(order=order).first()

            if funding:
                funding.status = "Completed"
                funding.save()

                print("FUNDING UPDATED:", funding.id)

                # Send email
                student = funding.student
                sponsor = funding.sponsor
                amount = funding.amount

                if student and student.user.email:
                    send_mail(
                        "You have received sponsorship funding!",
                        f"You received Rs. {amount} from {sponsor.username}",
                        "sponsor@example.com",
                        [student.user.email],
                        fail_silently=True,
                    )

    except Exception as e:
        print("DB ERROR:", e)
        messages.error(request, "Something went wrong.")
        return redirect("sponsor_dashboard")

    messages.success(request, "Payment successful!")
    return redirect("sponsor_dashboard")

@login_required
def sponsor_payment_fail(request):

    """
    Called by eSewa after failed payment.
    """
    messages.error(request, "Payment failed. Please try again.")
    return redirect("sponsor_dashboard")

def apply_funding(course, amount_to_use):
    remaining = amount_to_use

    fundings = Funding.objects.select_for_update().filter(course=course, status="Completed").order_by('id')

    for f in fundings:
        available = f.amount - f.used_amount

        if available <= 0:
            continue

        use = min(available, remaining)

        f.used_amount += use
        f.save()

        remaining -= use

        if remaining == 0:
            break

def update_enrollment_progress(student, course):
    enrollment = Enrollment.objects.get(student=student, course=course)
    lessons = course.modules.prefetch_related('module_lessons')
    total_lessons = sum(module.module_lessons.count() for module in lessons)
    completed_lessons = 0

    for module in lessons:
        for lesson in module.module_lessons.all():
            progress = LessonProgress.objects.filter(student=student, lesson=lesson).first()
            if progress and progress.status == "Completed":
                completed_lessons += 1

    enrollment.progress = round((completed_lessons / total_lessons) * 100, 1) if total_lessons > 0 else 0
    enrollment.completed = enrollment.progress == 100
    if enrollment.completed:
        enrollment.completed_at = timezone.now()
    enrollment.save()

def get_total_revenue(courses):
    return Enrollment.objects.filter(
        course__in=courses,
        completed=True
    ).aggregate(
        total=Sum('course__price')
    )['total'] or 0

@login_required
def instructor_analytics(request):
    instructor = request.user

    courses = Course.objects.filter(instructor=instructor)

    enrollments = Enrollment.objects.filter(course__in=courses)

    #  Course-wise revenue
    revenue_data = enrollments.values(
        'course__title'
    ).annotate(
        students=Count('student'),
        revenue=Sum('course__price') 
    )

    df = pd.DataFrame(list(revenue_data))

    #  Top selling courses
    top_courses = df.sort_values(by='students', ascending=False).head(5)

    #  Total revenue
    total_revenue = get_total_revenue(courses)

    # Prepare chart data
    chart_labels = df['course__title'].tolist() if not df.empty else []
    chart_values = df['students'].tolist() if not df.empty else []

    context = {
        "courses": courses,
        "total_revenue": total_revenue,
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "top_courses": top_courses.to_dict(orient='records'),
    }

    return render(request, "instructor_analytics.html", context)

def admin_dashboard(request):   
    courses = Course.objects.select_related('instructor', 'category')\
        .order_by('-created_at')[:5]
    
    students = User.objects.filter(profile__role='student')\
    
    
    total_students = User.objects.filter(profile__role='student').count()


    course_data = []
    for course in courses:
        student_count = Enrollment.objects.filter(course=course).count()

        course_data.append({
            'course': course,
            'student_count': student_count,
        })

    # total student based on roles
    total_students = UserProfile.objects.filter(role='student').count()

    # total courses
    total_courses = Course.objects.count()

    # total revenue
    total_revenue = Order.objects.filter(status="Completed").aggregate(total=Sum('amount'))['total'] or 0

    # pending approvals
    pending_approvals = Order.objects.filter(status="Pending").count()

    context = {
        'total_students': total_students,
        'total_courses': total_courses,
        'total_revenue': total_revenue,
        'pending_approvals': pending_approvals,
        'course_data': course_data,
        'students': students,
        'total_students': total_students,
    }
    return render(request, 'admin/index.html', context)

@login_required
def export_report_pdf(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="report.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # Header
    p.setFont("Helvetica-Bold", 18)
    p.drawString(200, 800, "Admin Dashboard Report")

    p.setFont("Helvetica", 12)

    # Data
    total_students = UserProfile.objects.count()
    total_courses = Course.objects.count()

    total_revenue = Funding.objects.filter(status="Completed").aggregate(
        total=models.Sum('amount')
    )['total'] or 0

    pending_approvals = Course.objects.filter(is_published=False).count()

    y = 750

    p.drawString(50, y, f"Total Students: {total_students}")
    y -= 25

    p.drawString(50, y, f"Total Courses: {total_courses}")
    y -= 25

    p.drawString(50, y, f"Total Revenue: Rs. {total_revenue}")
    y -= 25

    p.drawString(50, y, f"Pending Approvals: {pending_approvals}")
    y -= 40

    # Course Section
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y, "Recent Courses:")
    y -= 25

    p.setFont("Helvetica", 10)

    courses = Course.objects.all().order_by('-id')[:10]

    for course in courses:
        if y < 100:
            p.showPage()
            y = 800

        p.drawString(
            50,
            y,
            f"{course.title} | Instructor: {course.instructor} | Price: Rs.{course.price}"
        )
        y -= 20

    # Footer
    p.setFont("Helvetica-Oblique", 9)
    p.drawString(200, 40, "Generated by Admin Dashboard System")

    p.showPage()
    p.save()

    return response