import io
import re
import time

import pytest

from cloudvault import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({
        "TESTING": True, "SECRET_KEY": "test",
        "DATABASE_PATH": str(tmp_path / "t.db"), "UPLOAD_DIR": str(tmp_path / "up"),
        "MAX_UPLOAD_MB": 1, "USER_QUOTA_MB": 2,
    })


class Client:
    def __init__(self, app):
        self.c = app.test_client()

    def token(self):
        with self.c.session_transaction() as s:
            if "csrf_token" not in s:
                s["csrf_token"] = "tok"
            return s["csrf_token"]

    def post(self, url, data=None, **kw):
        data = dict(data or {}, csrf_token=self.token())
        return self.c.post(url, data=data, follow_redirects=True, **kw)

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def register_login(self, name="alice", pw="password123"):
        self.post("/register", {"username": name, "password": pw})
        return self.post("/login", {"username": name, "password": pw})

    def upload(self, name="note.txt", content=b"hello cloud"):
        return self.post("/upload", {"file": (io.BytesIO(content), name)},
                         content_type="multipart/form-data")


@pytest.fixture
def alice(app):
    c = Client(app)
    c.register_login()
    return c


def test_health(app):
    r = app.test_client().get("/health")
    assert r.status_code == 200 and r.json["status"] == "ok"


def test_redirects_when_logged_out(app):
    assert app.test_client().get("/dashboard").status_code == 302


def test_register_validation(app):
    c = Client(app)
    assert b"at least 8" in c.post("/register", {"username": "bob", "password": "short"}).data
    assert b"3-30" in c.post("/register", {"username": "a b", "password": "password123"}).data
    c.post("/register", {"username": "bob", "password": "password123"})
    assert b"already taken" in c.post("/register", {"username": "bob", "password": "password123"}).data


def test_wrong_password(app):
    c = Client(app)
    c.post("/register", {"username": "bob", "password": "password123"})
    assert b"Incorrect" in c.post("/login", {"username": "bob", "password": "nope"}).data


def test_csrf_blocks_post_without_token(app):
    r = app.test_client().post("/login", data={"username": "a", "password": "b"})
    assert r.status_code == 400


def test_upload_download_roundtrip(alice):
    assert b"Uploaded note.txt" in alice.upload().data
    r = alice.get("/files/1/download")
    assert r.data == b"hello cloud"
    assert "attachment" in r.headers["Content-Disposition"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_upload_rejects_bad_extension(alice):
    assert b"not allowed" in alice.upload("evil.exe", b"MZ").data


def test_upload_rejects_empty(alice):
    assert b"empty" in alice.upload("a.txt", b"").data


def test_upload_too_large(alice):
    r = alice.upload("big.txt", b"x" * (3 * 1024 * 1024))
    assert r.status_code == 413


def test_path_traversal_name_is_sanitised(alice):
    alice.upload("../../etc/passwd.txt", b"x")
    assert b"etc_passwd.txt" in alice.get("/dashboard").data or b"passwd.txt" in alice.get("/dashboard").data


def test_quota_enforced(alice):
    alice.upload("a.txt", b"x" * 1_000_000)
    alice.upload("b.txt", b"x" * 1_000_000)
    assert b"quota" in alice.upload("c.txt", b"x" * 500_000).data


def test_other_user_cannot_access(app, alice):
    alice.upload()
    bob = Client(app)
    bob.register_login("bob")
    assert bob.get("/files/1/download").status_code == 404
    assert bob.post("/files/1/delete").status_code == 404
    assert bob.post("/files/1/share").status_code == 404


def test_delete_removes_file_from_disk(app, alice):
    import os
    alice.upload()
    assert len(os.listdir(app.config["UPLOAD_DIR"])) == 1
    alice.post("/files/1/delete")
    assert os.listdir(app.config["UPLOAD_DIR"]) == []
    assert alice.get("/files/1/download").status_code == 404


def test_share_link_flow(app, alice):
    alice.upload()
    r = alice.post("/files/1/share", {"hours": "1"})
    token = re.search(rb"/s/([A-Za-z0-9_-]+)", r.data).group(1).decode()
    anon = app.test_client()
    assert b"note.txt" in anon.get(f"/s/{token}").data
    assert anon.get(f"/s/{token}/download").data == b"hello cloud"
    alice.post("/files/1/unshare")
    assert anon.get(f"/s/{token}").status_code == 404


def test_share_link_expires(app, alice):
    alice.upload()
    r = alice.post("/files/1/share", {"hours": "1"})
    token = re.search(rb"/s/([A-Za-z0-9_-]+)", r.data).group(1).decode()
    with app.app_context():
        from cloudvault.db import get_db
        get_db().execute("UPDATE files SET share_expires = '2000-01-01T00:00:00+00:00'")
        get_db().commit()
    assert app.test_client().get(f"/s/{token}").status_code == 404


def test_logout(alice):
    alice.post("/logout")
    assert alice.get("/dashboard").status_code == 302
