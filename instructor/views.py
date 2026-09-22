from django.shortcuts import render, redirect, get_object_or_404
from lms.models import *
from django.contrib.auth.decorators import login_required
from lms.utils import *
from lms.forms import *
from django.contrib import messages
from django.db.models import Q, Count, Avg, Min
from django.contrib.auth import update_session_auth_hash
import pandas as pd

# Create your views here.

def get_total_revenue(courses):
    return Enrollment.objects.filter(
        course__in=courses,
        completed=True
    ).aggregate(
        total=Sum('course__price')
    )['total'] or 0

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

def assignment_edit(request, assignment_id):
    pass

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
def instructor_analytics(request):
    instructor = request.user

    courses = Course.objects.filter(instructor=instructor)
    enrollments = Enrollment.objects.filter(course__in=courses)

    # Course-wise revenue
    revenue_data = enrollments.values(
        'course__title'
    ).annotate(
        students=Count('student'),
        revenue=Sum('course__price')
    )

    df = pd.DataFrame(list(revenue_data))

    # Rename columns for template-friendly keys
    if not df.empty:
        df.rename(columns={"course__title": "course_title"}, inplace=True)

    # Top selling courses
    top_courses = df.sort_values(by='students', ascending=False).head(5) if not df.empty else pd.DataFrame()

    # Total revenue
    total_revenue = get_total_revenue(courses)

    # Prepare chart data safely
    chart_labels = df['course_title'].tolist() if 'course_title' in df else []
    chart_values = df['students'].tolist() if 'students' in df else []

    context = {
        "courses": courses,
        "total_revenue": total_revenue,
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "top_courses": top_courses.to_dict(orient='records'),
    }

    return render(request, "instructor_analytics.html", context)