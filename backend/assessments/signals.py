from django.contrib.auth.signals import user_logged_in
from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from .audit import record_audit_event
from .models import AuditEvent
from .roles import ROLE_DEFINITIONS


@receiver(user_logged_in)
def audit_user_login(sender, request, user, **kwargs):
    record_audit_event(request=request, actor=user, action=AuditEvent.Action.LOGIN, target=user, target_type="User")


@receiver(m2m_changed)
def audit_group_membership_change(sender, instance, action, reverse, model, pk_set, **kwargs):
    User = get_user_model()
    if sender is not User.groups.through:
        return
    if action not in {"post_add", "post_remove"} or not pk_set:
        return

    audit_action = AuditEvent.Action.ROLE_ASSIGNED if action == "post_add" else AuditEvent.Action.ROLE_REMOVED
    if reverse:
        group_name = getattr(instance, "name", "")
        if group_name not in ROLE_DEFINITIONS:
            return
        users = User.objects.filter(pk__in=pk_set)
        for user in users:
            record_audit_event(
                action=audit_action,
                target=user,
                target_type="User",
                metadata={"groups": [group_name]},
            )
        return

    group_names = list(model.objects.filter(pk__in=pk_set, name__in=ROLE_DEFINITIONS.keys()).values_list("name", flat=True))
    if group_names:
        record_audit_event(
            action=audit_action,
            target=instance,
            target_type="User",
            metadata={"groups": group_names},
        )
