import bcrypt
from sqlalchemy.orm import Session
from fastapi import Request
from fastapi.responses import RedirectResponse
from models.user import User


def require_auth(request: Request):
    """FastAPI dependency: ensure the request is authenticated.

    Raises HTTPException(401) when there is no logged-in user. A global
    exception handler (registered in main.py) converts 401 into a redirect to
    /auth/login. This prevents endpoints from silently operating under
    user_id=0 (which made saved keys appear to 'disappear' after re-login).
    """
    user_id = request.session.get("user_id")
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if user and verify_password(password, user.hashed_password):
        return user
    return None


def create_user(db: Session, username: str, email: str, password: str) -> User:
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        is_admin=False,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_all_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.username).all()


def update_user_password(db: Session, user_id: int, new_password: str) -> User | None:
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.hashed_password = hash_password(new_password)
        db.commit()
        db.refresh(user)
    return user
