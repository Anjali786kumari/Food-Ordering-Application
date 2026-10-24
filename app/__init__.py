from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from config import Config
from .extensions import jwt
from .store import init_store


def create_app(config_object=Config):
    app = Flask(
        __name__,
        static_folder="static",
        static_url_path="/static"
    )

    app.config.from_object(config_object)
    app.config.setdefault("MAX_CONTENT_LENGTH", 5 * 1024 * 1024)

    CORS(app)
    jwt.init_app(app)
    init_store(app)

    from .routes.admin import bp as admin_bp
    from .routes.auth import bp as auth_bp
    from .routes.cart import bp as cart_bp
    from .routes.menu import bp as menu_bp
    from .routes.orders import bp as orders_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(menu_bp, url_prefix="/api/menu")
    app.register_blueprint(cart_bp, url_prefix="/api/cart")
    app.register_blueprint(orders_bp, url_prefix="/api/orders")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    @app.get("/")
    def home():
        return send_from_directory(app.root_path, "index.html")

    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify(error="Authentication required", detail=reason), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify(error="Invalid token", detail=reason), 401

    @jwt.expired_token_loader
    def expired_token(_header, _payload):
        return jsonify(error="Token has expired"), 401

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify(error="Resource not found"), 404

    @app.errorhandler(413)
    def too_large(_e):
        return jsonify(
            error="Image too large. Maximum upload size is 5 MB."
        ), 413

    @app.errorhandler(500)
    def server_error(_e):
        app.logger.exception("Unhandled server error")
        return jsonify(error="Internal server error"), 500

    return app