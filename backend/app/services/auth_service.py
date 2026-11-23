from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User


def register_user(db: Session, email: str, password: str) -> User | None:
    normalized_email = email.strip().casefold()
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        return None

    new_user = User(
        email=normalized_email,
        hashed_password=hash_password(password),
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.query(User).filter(User.email == normalized_email).first():
            return None
        raise

    db.refresh(new_user)
    return new_user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    normalized_email = email.strip().casefold()
    user = db.query(User).filter(User.email == normalized_email).first()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
