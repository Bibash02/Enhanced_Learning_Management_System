from django.shortcuts import render, redirect, get_object_or_404
from lms.models import *
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models import Q, Count, Avg, Min
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import uuid
from decimal import Decimal
from django.conf import settings
from django.urls import reverse
from lms.utils import *
import json
from lms.forms import *
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash

# Create your views here.
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
    return render(request, 'students/student_dashboard.html', context)

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
    return render(request, 'students/course_list.html', context)

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
    return render(request, 'students/enrolled_course.html', context)

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

    return render(request, 'students/course_learn.html', context)

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

    return render(request, "students/lesson_detail.html", context)

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

    return render(request, 'students/checkout.html', context)

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

        return render(request, "students/esewa_payment.html", {
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
        return render(request, "students/esewa_failed.html", {
            "message": "No payment data received."
        })

    try:
        decoded_data = base64.b64decode(encoded_data).decode("utf-8")
        payment_data = json.loads(decoded_data)

        print("PAYMENT DATA:", payment_data)

        transaction_uuid = payment_data.get("transaction_uuid")
        status = payment_data.get("status", "").upper()

        if not transaction_uuid:
            return render(request, "students/esewa_failed.html", {
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

            return render(request, "students/esewa_failed.html", {
                "message": f"Payment not completed. Status: {status}"
            })

    except Exception as e:
        print("ERROR:", e)
        return render(request, "students/esewa_failed.html", {
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
    
    return render(request, "students/esewa_failed.html", {"order": order})

@login_required
def payment_history(request):
    pass

def some_error_page(request):
    return render(request, "students/error1.html")

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
    return render(request, 'students/student_profile.html', context)

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
    return render(request, 'students/update_student_profile.html', context)

def change_student_password(request):
    pass

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

    return render(request, "students/completed_courses.html", {"completed_courses": completed})

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
    return render(request, 'students/pending_assignment.html', context)