"""Request context for storing user information across async calls."""

from contextvars import ContextVar

# Context variable to store the current user ID for the request
current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)


def get_current_user() -> str | None:
    """Get the current user ID from request context.
    
    Returns:
        User ID (OAuth subject) if set, None otherwise
    """
    return current_user_id.get()


def set_current_user(user_id: str | None):
    """Set the current user ID for this request context.
    
    Args:
        user_id: OAuth user ID (subject claim) or None to clear
    """
    current_user_id.set(user_id)
