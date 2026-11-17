import functools
import re

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db, utcnow

bp = Blueprint("auth", __name__)
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


@bp.before_app_request
def load_user():
    uid = session.get("user_id")
    g.user = None
    if uid is not None:
        g.user = get_db().execute("SELECT id, username FROM users WHERE id = ?", (uid,)).fetchone()


@bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        error = None
        if not USERNAME_RE.match(username):
            error = "Username must be 3-30 characters: letters, numbers or underscore."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        else:
            try:
                get_db().execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, generate_password_hash(password), utcnow().isoformat()))
                get_db().commit()
            except Exception:
                error = "That username is already taken."
        if error is None:
            flash("Account created. Please log in.", "ok")
            return redirect(url_for("auth.login"))
        flash(error, "error")
    return render_template("register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect username or password.", "error")
        else:
            session.clear()  # prevents session fixation
            session["user_id"] = user["id"]
            return redirect(url_for("files.dashboard"))
    return render_template("login.html")


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
