"""Authentication business rules: registration validation, hashing, login.

Passwords are hashed with Werkzeug's `generate_password_hash` (scrypt by
default) before they ever reach the repository layer. Plaintext passwords are
never stored, logged, or returned.
"""

import re

from werkzeug.security import check_password_hash, generate_password_hash

from repositories import user_repository

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MIN_PASSWORD_LENGTH = 8
MAX_NAME_LENGTH = 150
MAX_EMAIL_LENGTH = 150

# Shown for every failed login, whether the email is unknown or the password is
# wrong. Never reveal which one it was.
GENERIC_LOGIN_ERROR = "Invalid email or password."


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_registration(
    full_name: str, email: str, password: str, confirm_password: str
) -> list[str]:
    """Server-side validation for registration. Returns a list of errors.

    The register page also checks the password match in JavaScript, but that is
    a convenience only — this function is the authority and re-checks everything.
    """
    errors: list[str] = []

    full_name = (full_name or "").strip()
    email = normalize_email(email)

    if not full_name:
        errors.append("Full name is required.")
    elif len(full_name) > MAX_NAME_LENGTH:
        errors.append(f"Full name must be {MAX_NAME_LENGTH} characters or fewer.")

    if not email:
        errors.append("Email is required.")
    elif len(email) > MAX_EMAIL_LENGTH:
        errors.append(f"Email must be {MAX_EMAIL_LENGTH} characters or fewer.")
    elif not EMAIL_PATTERN.match(email):
        errors.append("Enter a valid email address.")

    if not password:
        errors.append("Password is required.")
    elif len(password) < MIN_PASSWORD_LENGTH:
        errors.append(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )

    if password != confirm_password:
        errors.append("Passwords do not match.")

    # Only hit the database if the email itself is well-formed.
    if email and not errors:
        if user_repository.email_exists(email):
            errors.append("An account with that email already exists.")

    return errors


def register(full_name: str, email: str, password: str) -> int:
    """Hash the password and create the user. Returns the new user id.

    Assumes `validate_registration` has already passed.
    """
    return user_repository.create(
        full_name=(full_name or "").strip(),
        email=normalize_email(email),
        password_hash=generate_password_hash(password),
    )


def authenticate(email: str, password: str) -> dict | None:
    """Return the user dict on success, None on any failure.

    A single None result covers both "no such email" and "wrong password" so the
    route layer cannot accidentally leak which one occurred.
    """
    user = user_repository.get_by_email(normalize_email(email))
    if user is None:
        return None
    if not check_password_hash(user["password_hash"], password or ""):
        return None
    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
    }


def get_profile(user_id: int) -> dict | None:
    """Fetch the display data for the profile page."""
    return user_repository.get_by_id(user_id)
