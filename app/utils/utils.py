# backend/app/utils/security.py

from passlib.context import CryptContext
from sqlalchemy.orm import Session
from typing import Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_role_id_by_name(db: Session, role_name: str) -> Optional[int]:
    """
    Get role_id from the roles table by role name.
    Maps user input like 'CUSTOMER', 'VENDOR', 'ADMIN', 'FREELANCE' to role IDs.
    """
    from .. import models

    # Normalize the role name to uppercase
    role_name_normalized = role_name.upper()

    # Query the role from the database
    role = db.query(models.Role).filter(models.Role.name == role_name_normalized).first()

    if role:
        return role.id

    # If role doesn't exist, return None
    return None


def ensure_roles_exist(db: Session):
    """
    Ensure all required roles exist in the database.
    Should be called during application startup or migrations.
    """
    from .. import models

    required_roles = [
        {"name": "CUSTOMER", "description": "Customer role for booking services"},
        {"name": "VENDOR", "description": "Vendor role for managing salons"},
        {"name": "ADMIN", "description": "Administrator role with full access"},
        {"name": "FREELANCE", "description": "Freelancer role for independent service providers"}
    ]

    for role_data in required_roles:
        existing_role = db.query(models.Role).filter(models.Role.name == role_data["name"]).first()
        if not existing_role:
            new_role = models.Role(**role_data)
            db.add(new_role)

    db.commit()
