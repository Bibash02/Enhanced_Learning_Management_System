# lms_api/permissions.py
from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Allows Django staff and superusers to manage every API role."""

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and (user.is_staff or user.is_superuser)


class IsStudent(BasePermission):
    """
    Allows access only to users with role 'student'.
    """
    def has_permission(self, request, view):
        return IsAdmin().has_permission(request, view) or (
            hasattr(request.user, 'profile') and request.user.profile.role == 'student'
        )

class IsInstructor(BasePermission):
    """
    Allows access only to users with role 'instructor'.
    """
    def has_permission(self, request, view):
        return IsAdmin().has_permission(request, view) or (
            hasattr(request.user, 'profile') and request.user.profile.role == 'instructor'
        )

class IsSponsor(BasePermission):
    """
    Allows access only to users with role 'sponsor'.
    """
    def has_permission(self, request, view):
        return IsAdmin().has_permission(request, view) or (
            hasattr(request.user, 'profile') and request.user.profile.role == 'sponsor'
        )
