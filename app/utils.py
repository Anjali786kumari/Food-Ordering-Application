from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request


def role_required(role: str):
    """Allow only users whose JWT carries the given role claim."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            if get_jwt().get("role") != role:
                return jsonify(error=f"Forbidden: {role} access required"), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def current_user_id() -> int:
    return int(get_jwt_identity())
