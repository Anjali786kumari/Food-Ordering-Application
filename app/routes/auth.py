import re
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from ..store import col, next_id, now

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def public_user(u):
    return {"id":u["id"],"name":u["name"],"email":u["email"],"role":u["role"]}

@bp.post("/register")
def register():
    data=request.get_json(silent=True) or {}
    name=(data.get("name") or "").strip()
    email=(data.get("email") or "").strip().lower()
    password=data.get("password") or ""
    if not name or not EMAIL_RE.match(email):
        return jsonify(error="A name and a valid email are required"),400
    if len(password)<6:
        return jsonify(error="Password must be at least 6 characters"),400
    from werkzeug.security import generate_password_hash
    if col("users").find_one({"email":email}):
        return jsonify(error="Email already registered"),409
    user={"id":next_id("users"),"name":name,"email":email,
          "password_hash":generate_password_hash(password),"role":"customer","created_at":now()}
    col("users").insert_one(user)
    return jsonify(message="Registered successfully",user=public_user(user)),201

@bp.post("/login")
def login():
    from werkzeug.security import check_password_hash
    data=request.get_json(silent=True) or {}
    email=(data.get("email") or "").strip().lower()
    user=col("users").find_one({"email":email})
    if not user or not check_password_hash(user["password_hash"],data.get("password") or ""):
        return jsonify(error="Invalid email or password"),401
    token=create_access_token(identity=str(user["id"]),additional_claims={"role":user["role"]})
    return jsonify(access_token=token,token_type="Bearer",user=public_user(user))

@bp.get("/me")
@jwt_required()
def me():
    user=col("users").find_one({"id":int(get_jwt_identity())})
    if not user: return jsonify(error="User not found"),404
    return jsonify(user=public_user(user))
