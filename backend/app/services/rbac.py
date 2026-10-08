from __future__ import annotations

from app.models.enums import Permission, RoleName

# Static role -> permission matrix. Super admins additionally bypass all
# checks (see app.api.deps.require_permission).
ROLE_PERMISSIONS: dict[str, set[str]] = {
    RoleName.SUPER_ADMIN.value: {p.value for p in Permission},
    RoleName.SECURITY_ADMINISTRATOR.value: {p.value for p in Permission},
    RoleName.CAMPAIGN_MANAGER.value: {
        Permission.CAMPAIGN_CREATE.value,
        Permission.CAMPAIGN_LAUNCH.value,
        Permission.CAMPAIGN_MANAGE.value,
        Permission.RECIPIENT_MANAGE.value,
        Permission.TEMPLATE_MANAGE.value,
        Permission.REPORT_VIEW.value,
        Permission.REPORT_GENERATE.value,
        Permission.ANALYTICS_VIEW.value,
    },
    RoleName.ANALYST.value: {
        Permission.REPORT_VIEW.value,
        Permission.REPORT_GENERATE.value,
        Permission.ANALYTICS_VIEW.value,
    },
    RoleName.READ_ONLY.value: {
        Permission.REPORT_VIEW.value,
        Permission.ANALYTICS_VIEW.value,
    },
}


def role_has_permission(role_name: str, permission: Permission) -> bool:
    return permission.value in ROLE_PERMISSIONS.get(role_name, set())
