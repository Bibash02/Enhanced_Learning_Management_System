from django.db.models import Sum
from decimal import Decimal
from django.db import transaction
from .models import Funding, Course, UserProfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
from django.core.mail import send_mail
from django.conf import settings

def generate_invoice(payment):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Payment Invoice")
    y -= 40

    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"Student: {payment.student.username}")
    y -= 20
    c.drawString(50, y, f"Course: {payment.course.title}")
    y -= 20
    c.drawString(50, y, f"Amount: Rs. {payment.amount}")
    y -= 20
    c.drawString(50, y, f"Payment Method: {payment.payment_method}")
    y -= 20
    c.drawString(50, y, f"Transaction ID: {payment.transaction_uuid}")
    y -= 20
    c.drawString(50, y, f"Status: {payment.status}")
    y -= 20
    c.drawString(50, y, f"Date: {payment.created_at.strftime('%Y-%m-%d %H:%M')}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# app/utils.py

def get_course_total_funded(course):
    """
    Sum of COMPLETED fundings for the course.
    """
    res = Funding.objects.filter(course=course, status="Completed").aggregate(total=Sum('amount'))
    total = res['total'] or Decimal('0.00')
    return total

def get_course_remaining(course):
    """
    Remaining amount needed to fully fund the course.
    (course.price - funded). Never below 0.
    """
    funded = get_course_total_funded(course)
    remaining = (course.price or Decimal('0.00')) - funded
    return remaining if remaining > 0 else Decimal('0.00')

def get_student_wallet(user_profile):
    """
    Student wallet = sum of Completed fundings where student is the target.
    Note: we will treat negative Funding.amount as wallet usage.
    """
    res = Funding.objects.filter(student=user_profile, status="Completed").aggregate(total=Sum('amount'))
    total = res['total'] or Decimal('0.00')
    return total

@transaction.atomic
def apply_student_wallet_for_enrollment(user_profile, course, enroll_action_callback):
    """
    Attempt to pay for `course` using student's wallet.
    enroll_action_callback: a callable performing the actual enrollment (must be safe).
    Returns tuple (success: bool, message: str)
    This function:
      - computes effective price for course (course.price - course funded)
      - checks student's wallet
      - if wallet >= effective price => create a negative Funding to consume wallet, call enroll_action_callback, return success
      - else return False, message
    """
    from decimal import Decimal
    remaining_course_price = get_course_remaining(course)
    wallet = get_student_wallet(user_profile)

    if wallet <= Decimal('0.00'):
        return False, "Student has no sponsorship funds available."

    # Price to charge this student (effective price)
    charge_amount = remaining_course_price if remaining_course_price > 0 else Decimal('0.00')

    if wallet < charge_amount:
        return False, f"Insufficient sponsorship wallet balance (need {charge_amount}, have {wallet})."

    # Deduct from student wallet by creating a Completed Funding with negative amount
    Funding.objects.create(
        sponsor=user_profile.user,   # we can set sponsor as student's own user for wallet deductions
        student=user_profile,
        course=course,  # optional: tie to course for traceability
        amount=-charge_amount,
        status="Completed"
    )

    # Optionally call the enrollment action (create Enrollment model, etc.)
    try:
        enroll_action_callback()
    except Exception as e:
        # If enrollment fails, rollback by raising error (transaction.atomic will rollback)
        raise

    return True, "Enrollment completed using sponsorship wallet."

def send_notification_email(to_email, subject, message):
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [to_email],
        fail_silently=False,
    )