from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Permission, RoleName
from app.models.identity import Permission as PermissionModel, Role
from app.services.rbac import ROLE_PERMISSIONS


def seed_rbac(db: Session) -> None:
    existing_codes = {p.code for p in db.execute(select(PermissionModel)).scalars().all()}
    for perm in Permission:
        if perm.value not in existing_codes:
            db.add(PermissionModel(code=perm.value, description=perm.value.replace(":", " ").title()))
    db.commit()

    permission_rows = {p.code: p for p in db.execute(select(PermissionModel)).scalars().all()}

    existing_roles = {r.name for r in db.execute(select(Role)).scalars().all()}
    for role_name, perm_codes in ROLE_PERMISSIONS.items():
        if role_name in existing_roles:
            continue
        role = Role(name=role_name, description=role_name.replace("_", " ").title())
        role.permissions = [permission_rows[c] for c in perm_codes if c in permission_rows]
        db.add(role)
    db.commit()
