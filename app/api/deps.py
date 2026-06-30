from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserStatus
from app.repositories.user import UserRepository
from app.security.jwt import verify_access_token
from app.security import rbac

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    payload = verify_access_token(token)
    user_id = int(payload["sub"])
    repo = UserRepository(session)
    user = await repo.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="کاربر یافت نشد")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="حساب کاربری غیرفعال است")
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    rbac.require_admin(current_user)
    return current_user


async def require_reseller(current_user: User = Depends(get_current_user)) -> User:
    rbac.require_reseller(current_user)
    return current_user


async def require_l1_reseller(current_user: User = Depends(get_current_user)) -> User:
    rbac.require_l1_reseller(current_user)
    return current_user
