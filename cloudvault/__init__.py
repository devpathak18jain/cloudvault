"""CloudVault - a small cloud file storage and sharing service."""
import os
import secrets

from flask import Flask, abort, jsonify, render_template, request, session

from . import auth, db, files
from .storage import make_storage


def create_app(test_config=None):
    app = Flask(__name__)
    env = os.environ.get
    app.config.update(
        SECRET_KEY=env("SECRET_KEY", "dev-only-change-me"),
        DATABASE_PATH=env("DATABASE_PATH", os.path.join(os.getcwd(), "data", "cloudvault.db")),
        STORAGE_BACKEND=env("STORAGE_BACKEND", "local"),  # local | s3
        UPLOAD_DIR=env("UPLOAD_DIR", os.path.join(os.getcwd(), "data", "uploads")),
        S3_BUCKET=env("S3_BUCKET", ""),
        AWS_REGION=env("AWS_REGION", "ap-south-1"),
        MAX_UPLOAD_MB=int(env("MAX_UPLOAD_MB", "10")),
        USER_QUOTA_MB=int(env("USER_QUOTA_MB", "50")),
        ALLOWED_EXTENSIONS=set(
            env("ALLOWED_EXTENSIONS", "txt,pdf,png,jpg,jpeg,gif,csv,docx,pptx,xlsx,zip,md").split(",")
        ),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=env("COOKIE_SECURE", "0") == "1",
    )
    if test_config:
        app.config.update(test_config)
    app.config["MAX_CONTENT_LENGTH"] = (app.config["MAX_UPLOAD_MB"] + 1) * 1024 * 1024

    app.storage = make_storage(app.config)
    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(files.bp)

    # ---- CSRF protection for every state-changing request ----
    @app.before_request
    def csrf_protect():
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            sent = request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            if not expected or not secrets.compare_digest(sent, expected):
                abort(400, "Invalid or missing CSRF token. Reload the page and try again.")

    @app.context_processor
    def inject_globals():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        return {"csrf_token": session["csrf_token"], "config": app.config}

    # ---- Security headers ----
    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = "default-src 'self'"
        return resp

    # ---- Health check (used by Docker, load balancers, monitoring) ----
    @app.get("/health")
    def health():
        ok_db = True
        try:
            db.get_db().execute("SELECT 1")
        except Exception:
            ok_db = False
        ok_storage = app.storage.healthy()
        status = 200 if (ok_db and ok_storage) else 503
        return jsonify(status="ok" if status == 200 else "degraded",
                       database=ok_db, storage=ok_storage,
                       backend=app.config["STORAGE_BACKEND"]), status

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def handle_error(err):
        msg = {413: f"File too large. Maximum upload size is {app.config['MAX_UPLOAD_MB']} MB."}.get(
            err.code, getattr(err, "description", "Something went wrong."))
        return render_template("error.html", code=err.code, message=msg), err.code

    return app
