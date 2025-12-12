This project is an Enhanced Learning Management System (LMS) developed using Django and Python. It supports multiple user roles including Admin, Instructor, Student, and Sponsor, allowing for course management, student enrollment, sponsorship tracking, and more. The system is designed to facilitate online learning with features like authentication, analytics, notifications, and optional payment integration.
The objective is to create a robust platform where:

Instructors can manage courses and assessments.
Students can enroll in courses and complete assignments.
Sponsors can fund students and monitor their progress.
Admins oversee the entire platform.

Features

Database Design:
Custom schema designed based on research, including tables for users, courses, enrollments, assessments, sponsorships, and more.

CRUD Operations:
Full Create, Read, Update, Delete functionality for managing courses, users, assessments, and sponsorships.

Code Documentation:
All code includes proper comments and explanations for clarity and maintainability.

Data Filtering and Searching:
Students can search courses by name, instructor, or difficulty level.
Sponsors can filter students by status or progress.

Data Pagination:
Paginated views for course lists, student records, and sponsorship details to handle large datasets efficiently.

Authentication:
Role-based access control using Django Groups for Admin, Instructor, Student, and Sponsor roles.

Analytics:
Admin Dashboard: Displays metrics such as total users, active courses, and student enrollments.
Sponsor Dashboard: Shows sponsorship impact, student progress, and fund utilization.

Emailing:
Notifications to students about course deadlines and assessment results.
Progress reports emailed to sponsors.

Notifications:
Alerts for instructors on course completion rates and student engagement.
Notifications for students about new assignments and due dates.

Payment (Optional):
Integration with payment gateways for sponsors to fund courses or students.

Testing and Documentation:
Detailed API tests using tool Postman.
User and developer documentation provided.


Technologies Used

Backend: Django (Python web framework)
Database: PostgreSQL 
Authentication: Django's built-in auth system with Groups
Emailing: Django's email backend (e.g., SMTP integration)
Frontend: HTML/CSS/JavaScript (with Django templates); optional Bootstrap for styling
Other Libraries: Django REST Framework (if APIs are exposed), Celery (for background tasks like notifications, optional)
