from django.core.mail import send_mail
from django.conf import settings

def send_enrollment_email(student, instructor, course):
    subject = f"New Student Enrollment in {course.title}"
    message = (
        f"Hello {instructor.username},\n\n"
        f"{student.username} has enrolled in your course: {course.title}.\n\n"
        "Regards,\nYour LMS Team"
    )

    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,        # sender
        [instructor.email],              # receiver
        fail_silently=False,
    )
