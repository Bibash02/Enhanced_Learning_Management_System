from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from lms.models import User, UserProfile, SponsorProfile
from django.core.mail import send_mail
from django.conf import settings

# Create your views here.
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