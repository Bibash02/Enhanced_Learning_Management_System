# lms_api/permissions.py
from rest_framework.permissions import BasePermission

class IsStudent(BasePermission):
    """
    Allows access only to users with role 'student'.
    """
    def has_permission(self, request, view):
        return hasattr(request.user, 'profile') and request.user.profile.role == 'student'

class IsInstructor(BasePermission):
    """
    Allows access only to users with role 'instructor'.
    """
    def has_permission(self, request, view):
        return hasattr(request.user, 'profile') and request.user.profile.role == 'instructor'

class IsSponsor(BasePermission):
    """
    Allows access only to users with role 'sponsor'.
    """
    def has_permission(self, request, view):
        return hasattr(request.user, 'profile') and request.user.profile.role == 'sponsor'
