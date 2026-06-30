"""
Role-Based Access Control.

Permission checks are enforced in both the bot handlers and API endpoints.
Never rely solely on frontend button visibility.
"""

from fastapi import HTTPException, status
from app.models.user import UserRole, UserStatus


# ── Role sets ───────────────────────────────────────────────────────────────

ADMIN_ROLES = {UserRole.ADMIN}
L1_ROLES = {UserRole.RESELLER_L1, UserRole.RESELLER}       # legacy RESELLER = L1
L2_ROLES = {UserRole.RESELLER_L2}
ALL_RESELLER_ROLES = L1_ROLES | L2_ROLES
ALL_ROLES = ADMIN_ROLES | ALL_RESELLER_ROLES | {UserRole.CUSTOMER}


# ── FastAPI dependency helpers ───────────────────────────────────────────────

def _check_active(user) -> None:
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری غیرفعال یا مسدود است",
        )


def require_admin(user) -> None:
    _check_active(user)
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="⛔ دسترسی ندارید — فقط مدیر")


def require_reseller(user) -> None:
    _check_active(user)
    if user.role not in ALL_RESELLER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="⛔ دسترسی ندارید — فقط نمایندگان")


def require_l1_reseller(user) -> None:
    _check_active(user)
    if user.role not in L1_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="⛔ دسترسی ندارید — فقط نمایندگان سطح ۱",
        )


def require_admin_or_reseller(user) -> None:
    _check_active(user)
    if user.role not in (ADMIN_ROLES | ALL_RESELLER_ROLES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="⛔ دسترسی ندارید")


# ── Bot-level permission helpers (return bool, don't raise) ─────────────────

def bot_is_admin(db_user) -> bool:
    return db_user.role in ADMIN_ROLES and db_user.status == UserStatus.ACTIVE


def bot_is_reseller(db_user) -> bool:
    return db_user.role in ALL_RESELLER_ROLES and db_user.status == UserStatus.ACTIVE


def bot_is_l1(db_user) -> bool:
    return db_user.role in L1_ROLES and db_user.status == UserStatus.ACTIVE


def bot_is_l2(db_user) -> bool:
    return db_user.role in L2_ROLES and db_user.status == UserStatus.ACTIVE


def bot_is_admin_or_l1(db_user) -> bool:
    return bot_is_admin(db_user) or bot_is_l1(db_user)


def check_reseller_owns_customer(reseller, customer) -> bool:
    """IDOR guard: verify the reseller owns this customer."""
    return customer is not None and customer.reseller_id == reseller.id


def check_l1_owns_child(parent_reseller, child_reseller) -> bool:
    """Verify a L2 reseller belongs to this L1 parent."""
    return (
        child_reseller is not None
        and child_reseller.parent_reseller_id == parent_reseller.id
    )
