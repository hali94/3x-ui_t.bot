from functools import wraps
from fastapi import HTTPException, status
from app.models.user import UserRole, UserStatus


class Permission:
    ADMIN_ONLY = [UserRole.ADMIN]
    RESELLER_ONLY = [UserRole.RESELLER]
    ADMIN_OR_RESELLER = [UserRole.ADMIN, UserRole.RESELLER]
    ALL_ROLES = [UserRole.ADMIN, UserRole.RESELLER, UserRole.CUSTOMER]


def require_roles(*roles: UserRole):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user=None, **kwargs):
            if current_user is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="احراز هویت الزامی است")
            if current_user.status != UserStatus.ACTIVE:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="حساب کاربری غیرفعال است")
            if current_user.role not in roles:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="⛔ دسترسی ندارید")
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator


def check_reseller_ownership(reseller_id: int, current_user) -> None:
    if current_user.role == UserRole.ADMIN:
        return
    if current_user.reseller_profile is None or current_user.reseller_profile.id != reseller_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="⛔ دسترسی به این منبع ندارید")
