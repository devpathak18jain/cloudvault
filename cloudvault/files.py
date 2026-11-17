import mimetypes
import os
import secrets
import uuid
from datetime import timedelta

from flask import (Blueprint, Response, abort, current_app, flash, g,
                   redirect, render_template, request, url_for)
from werkzeug.utils import secure_filename

from .auth import login_required
from .db import get_db, utcnow

bp = Blueprint("files", __name__)
MB = 1024 * 1024


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


bp.add_app_template_filter(human_size, "human_size")


def _own_file_or_404(file_id):
    row = get_db().execute("SELECT * FROM files WHERE id = ? AND user_id = ?",
                           (file_id, g.user["id"])).fetchone()
    if row is None:
        abort(404, "File not found.")
    return row


def _send(row):
    resp = Response(current_app.storage.stream(row["storage_key"]),
                    mimetype=row["content_type"])
    resp.headers.set("Content-Disposition", "attachment", filename=row["original_name"])
    resp.headers["Content-Length"] = str(row["size"])
    return resp


def _share_is_live(row):
    if not row["share_token"]:
        return False
    if row["share_expires"] is None:
        return True
    return utcnow().isoformat() < row["share_expires"]


@bp.route("/")
def index():
    return redirect(url_for("files.dashboard" if g.user else "auth.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    rows = get_db().execute("SELECT * FROM files WHERE user_id = ? ORDER BY id DESC",
                            (g.user["id"],)).fetchall()
    files = [dict(r, share_live=_share_is_live(r)) for r in rows]
    used = sum(r["size"] for r in rows)
    quota = current_app.config["USER_QUOTA_MB"] * MB
    return render_template("dashboard.html", files=files, used=used, quota=quota,
                           percent=min(100, round(used * 100 / quota)))


@bp.post("/upload")
@login_required
def upload():
    cfg = current_app.config
    f = request.files.get("file")
    if f is None or not f.filename:
        flash("Choose a file first.", "error")
        return redirect(url_for("files.dashboard"))

    name = secure_filename(f.filename)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if not name or ext not in cfg["ALLOWED_EXTENSIONS"]:
        flash("File type not allowed. Allowed: " + ", ".join(sorted(cfg["ALLOWED_EXTENSIONS"])), "error")
        return redirect(url_for("files.dashboard"))

    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if size == 0:
        flash("That file is empty.", "error")
        return redirect(url_for("files.dashboard"))
    if size > cfg["MAX_UPLOAD_MB"] * MB:
        flash(f"File too large (max {cfg['MAX_UPLOAD_MB']} MB).", "error")
        return redirect(url_for("files.dashboard"))

    db = get_db()
    used = db.execute("SELECT COALESCE(SUM(size),0) FROM files WHERE user_id = ?",
                      (g.user["id"],)).fetchone()[0]
    if used + size > cfg["USER_QUOTA_MB"] * MB:
        flash(f"Storage quota of {cfg['USER_QUOTA_MB']} MB would be exceeded. Delete something first.", "error")
        return redirect(url_for("files.dashboard"))

    key = uuid.uuid4().hex
    current_app.storage.save(f.stream, key)
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    db.execute("INSERT INTO files (user_id, original_name, storage_key, size, content_type, created_at)"
               " VALUES (?, ?, ?, ?, ?, ?)",
               (g.user["id"], name, key, size, ctype, utcnow().isoformat()))
    db.commit()
    flash(f"Uploaded {name}.", "ok")
    return redirect(url_for("files.dashboard"))


@bp.get("/files/<int:file_id>/download")
@login_required
def download(file_id):
    return _send(_own_file_or_404(file_id))


@bp.post("/files/<int:file_id>/delete")
@login_required
def delete(file_id):
    row = _own_file_or_404(file_id)
    current_app.storage.delete(row["storage_key"])
    get_db().execute("DELETE FROM files WHERE id = ?", (file_id,))
    get_db().commit()
    flash(f"Deleted {row['original_name']}.", "ok")
    return redirect(url_for("files.dashboard"))


@bp.post("/files/<int:file_id>/share")
@login_required
def share(file_id):
    _own_file_or_404(file_id)
    try:
        hours = int(request.form.get("hours", "24"))
    except ValueError:
        hours = 24
    hours = max(1, min(hours, 24 * 30))
    token = secrets.token_urlsafe(16)
    expires = (utcnow() + timedelta(hours=hours)).isoformat()
    get_db().execute("UPDATE files SET share_token = ?, share_expires = ? WHERE id = ?",
                     (token, expires, file_id))
    get_db().commit()
    flash("Share link created: " + url_for("files.shared_page", token=token, _external=True), "ok")
    return redirect(url_for("files.dashboard"))


@bp.post("/files/<int:file_id>/unshare")
@login_required
def unshare(file_id):
    _own_file_or_404(file_id)
    get_db().execute("UPDATE files SET share_token = NULL, share_expires = NULL WHERE id = ?", (file_id,))
    get_db().commit()
    flash("Sharing turned off.", "ok")
    return redirect(url_for("files.dashboard"))


def _shared_or_404(token):
    row = get_db().execute("SELECT f.*, u.username FROM files f JOIN users u ON u.id = f.user_id "
                           "WHERE share_token = ?", (token,)).fetchone()
    if row is None or not _share_is_live(row):
        abort(404, "This link is invalid or has expired.")
    return row


@bp.get("/s/<token>")
def shared_page(token):
    return render_template("shared.html", f=_shared_or_404(token), token=token)


@bp.get("/s/<token>/download")
def shared_download(token):
    return _send(_shared_or_404(token))
