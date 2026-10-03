"""The three roles of the token model (FUNCTIONAL_SPEC 附录 A).

Kept in its own module so both `core.deps` (the auth seam) and the account
repository can depend on the names without importing each other.
"""

ROLE_USER = "user"
ROLE_DOCTOR = "doctor"
ROLE_ADMIN = "admin"

ROLES = (ROLE_USER, ROLE_DOCTOR, ROLE_ADMIN)
