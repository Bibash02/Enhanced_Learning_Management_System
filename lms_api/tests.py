from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from .permissions import IsAdmin, IsInstructor, IsSponsor, IsStudent


class RolePermissionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def request_for(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_staff_admin_passes_every_role_permission(self):
        request = self.request_for(
            SimpleNamespace(is_authenticated=True, is_staff=True, is_superuser=False)
        )

        for permission_class in (IsAdmin, IsStudent, IsInstructor, IsSponsor):
            with self.subTest(permission=permission_class.__name__):
                self.assertTrue(permission_class().has_permission(request, None))

    def test_superuser_passes_every_role_permission(self):
        request = self.request_for(
            SimpleNamespace(is_authenticated=True, is_staff=False, is_superuser=True)
        )

        for permission_class in (IsAdmin, IsStudent, IsInstructor, IsSponsor):
            with self.subTest(permission=permission_class.__name__):
                self.assertTrue(permission_class().has_permission(request, None))

    def test_role_user_does_not_pass_other_role_permissions(self):
        request = self.request_for(
            SimpleNamespace(
                is_authenticated=True,
                is_staff=False,
                is_superuser=False,
                profile=SimpleNamespace(role="student"),
            )
        )

        self.assertTrue(IsStudent().has_permission(request, None))
        self.assertFalse(IsInstructor().has_permission(request, None))
        self.assertFalse(IsSponsor().has_permission(request, None))

    def test_anonymous_user_does_not_pass_role_permissions(self):
        request = self.request_for(
            SimpleNamespace(is_authenticated=False, is_staff=False, is_superuser=False)
        )

        for permission_class in (IsAdmin, IsStudent, IsInstructor, IsSponsor):
            with self.subTest(permission=permission_class.__name__):
                self.assertFalse(permission_class().has_permission(request, None))

# Create your tests here.
