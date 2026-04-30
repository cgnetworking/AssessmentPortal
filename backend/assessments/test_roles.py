import unittest
import sys
import types


django_module = types.ModuleType("django")
django_http_module = types.ModuleType("django.http")
django_http_module.JsonResponse = object
sys.modules.setdefault("django", django_module)
sys.modules.setdefault("django.http", django_http_module)

from assessments.roles import ASSESSMENT_OPERATOR, PORTAL_ADMIN, is_portal_admin


class FakeGroupQuery:
    def __init__(self, names):
        self.names = names

    def values_list(self, *_args, **_kwargs):
        return self.names


class FakeGroups:
    def __init__(self, names):
        self.names = names

    def filter(self, **_kwargs):
        return FakeGroupQuery(self.names)


class FakeUser:
    def __init__(self, *, roles=(), is_superuser=False, is_authenticated=True):
        self.groups = FakeGroups(list(roles))
        self.is_superuser = is_superuser
        self.is_authenticated = is_authenticated


class PortalAdminRoleTests(unittest.TestCase):
    def test_portal_admin_group_can_view_process_logs(self):
        self.assertTrue(is_portal_admin(FakeUser(roles=[PORTAL_ADMIN])))

    def test_assessment_operator_cannot_view_process_logs(self):
        self.assertFalse(is_portal_admin(FakeUser(roles=[ASSESSMENT_OPERATOR])))

    def test_superuser_is_treated_as_portal_admin(self):
        self.assertTrue(is_portal_admin(FakeUser(is_superuser=True)))


if __name__ == "__main__":
    unittest.main()
