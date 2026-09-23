from django.urls import path
from .views import *
urlpatterns = [
    path('', home, name='home'),
    path('about', about, name='about'),

    path('admin/admin-dashboard', admin_dashboard, name='admin_dashboard'),
    path('admin/export-report', export_report_pdf, name='export_report_pdf'),
]