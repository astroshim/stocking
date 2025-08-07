from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jose import jwt, JWTError
from typing import Optional

from app.config import config

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/users/login")  # 토큰 발급 경로
ALGORITHM = "HS256"


# def get_current_user(token: str = Depends(api_key_header)):
#     try:
#         payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[ALGORITHM])
#         user_id: str = payload.get("sub")
#         if user_id is None:
#             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
#         return user_id
#     except JWTError:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

def get_current_user(authorization: Optional[str] = Depends(api_key_header)):
    """
    Authorization 헤더에서 토큰을 추출하여 사용자 ID를 반환합니다.
    토큰은 "Bearer {token}" 형식이거나 직접 토큰 값을 입력할 수 있습니다.
    """
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # "Bearer " 프리픽스가 있으면 제거
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: user ID missing",
                headers={"WWW-Authenticate": "Bearer"}
            )
        return user_id
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )