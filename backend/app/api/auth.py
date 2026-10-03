"""Minimal role auth via per-role API keys from the environment (FACULTY_API_KEY / STUDENT_API_KEY).
This is NOT a full identity system (no per-user accounts/sessions): reviewer identity comes from the
X-Reviewer header and student identity from X-Student-Roll. Replace with the college SSO for real use."""
import hmac
import os

from fastapi import Depends, Header, HTTPException


def _check(role_env: str, token: str | None) -> bool:
    key = os.getenv(role_env, "")
    return bool(key) and bool(token) and hmac.compare_digest(key, token)


def _bearer(authorization: str | None) -> str | None:
    return authorization[7:] if authorization and authorization.lower().startswith("bearer ") else None


def _configured() -> None:
    if not os.getenv("FACULTY_API_KEY") or not os.getenv("STUDENT_API_KEY"):
        raise HTTPException(503, "Auth is not configured: set FACULTY_API_KEY and STUDENT_API_KEY.")


class Actor:
    def __init__(self, role: str, name: str):
        self.role, self.name = role, name


def faculty(authorization: str | None = Header(default=None), x_reviewer: str = Header(default="faculty")) -> Actor:
    _configured()
    if not _check("FACULTY_API_KEY", _bearer(authorization)):
        raise HTTPException(401, "Faculty credentials required.")
    return Actor("faculty", x_reviewer.strip()[:100] or "faculty")


def student(authorization: str | None = Header(default=None), x_student_roll: str = Header(default="")) -> Actor:
    _configured()
    if not _check("STUDENT_API_KEY", _bearer(authorization)) or not x_student_roll.strip():
        raise HTTPException(401, "Student credentials and X-Student-Roll required.")
    return Actor("student", x_student_roll.strip())


def any_role(authorization: str | None = Header(default=None), x_reviewer: str = Header(default="faculty"),
             x_student_roll: str = Header(default="")) -> Actor:
    _configured()
    tok = _bearer(authorization)
    if _check("FACULTY_API_KEY", tok):
        return Actor("faculty", x_reviewer.strip()[:100] or "faculty")
    if _check("STUDENT_API_KEY", tok) and x_student_roll.strip():
        return Actor("student", x_student_roll.strip())
    raise HTTPException(401, "Credentials required.")
