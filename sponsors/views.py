from django.shortcuts import render, redirect, get_object_or_404
from lms.models import *
from lms.utils import *
from lms.signals import *
from lms.forms import *
from django.db.models import Q, Count, Avg, Min
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.http import HttpResponse
import uuid
import json
from django.urls import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# Create your views here.
def sponsor_dashboard(request):
    sponsor = request.user
    user_profile = request.user.profile

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
        "sponsor_name": user_profile.user.first_name or user_profile.user.username,
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

    return render(request, "sponsors/sponsor_dashboard.html", context)

@login_required
def sponsor_profile(request):
    sponsor = request.user  
    context = {
        "sponsor_name": sponsor.get_full_name() or sponsor.username,
    }
    return render(request, 'sponsors/sponsor_profile.html', context)

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

    return render(request, 'sponsors/update_sponsor_profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
    })

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
    return render(request, 'sponsors/fund_student.html', context)

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
    return render(request, 'sponsors/fund_student_detail.html', {
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
def fund_course_page(request):
    sponsor = request.user
    sponsor_profile = UserProfile.objects.get(user=sponsor)

    # Get all published courses
    courses = Course.objects.filter(is_published=True)

    context = {
        "sponsor_username": sponsor.get_full_name() or sponsor.username,
        "courses": courses,
    }
    return render(request, "sponsors/fund_course_page.html", context)

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
    return render(request, "sponsors/fund_course_checkout.html", context)

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

        return render(request, "sponsors/fund_course_process.html", context)

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
        return render(request, "sponsors/sponsor_checkout.html", {
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

        return render(request, "sponsors/sponsor_payment.html", {
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

    return render(request, "sponsors/student_profile_view.html", context)

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

    return render(request, "sponsors/course_profile_view.html", context)

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
    return render(request, "sponsors/funding_history.html", context)