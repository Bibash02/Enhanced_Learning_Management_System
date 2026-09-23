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
from students.views import apply_funding

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


def renew_sponsorship(request, student_id):
    pass

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

def about(request):
    return render(request, 'about.html')

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