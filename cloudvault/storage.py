"""Storage backends. The app only talks to this small interface, so the same
code runs on a laptop (local disk) or on AWS (Amazon S3)."""
import os
import re

CHUNK = 64 * 1024
_KEY_RE = re.compile(r"^[0-9a-f]{32}$")


class LocalStorage:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def _path(self, key):
        if not _KEY_RE.match(key):  # blocks path traversal
            raise ValueError("invalid storage key")
        return os.path.join(self.root, key)

    def save(self, fileobj, key):
        with open(self._path(key), "wb") as out:
            while chunk := fileobj.read(CHUNK):
                out.write(chunk)

    def stream(self, key):
        with open(self._path(key), "rb") as f:
            while chunk := f.read(CHUNK):
                yield chunk

    def delete(self, key):
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass

    def healthy(self):
        return os.path.isdir(self.root) and os.access(self.root, os.W_OK)


class S3Storage:
    """Amazon S3. Credentials come from the EC2 IAM role (no keys in code)."""

    def __init__(self, bucket, region, prefix="uploads/"):
        import boto3  # imported lazily so local mode needs no AWS library

        if not bucket:
            raise RuntimeError("S3_BUCKET must be set when STORAGE_BACKEND=s3")
        self.bucket, self.prefix = bucket, prefix
        self.client = boto3.client("s3", region_name=region)

    def _k(self, key):
        if not _KEY_RE.match(key):
            raise ValueError("invalid storage key")
        return self.prefix + key

    def save(self, fileobj, key):
        self.client.upload_fileobj(
            fileobj, self.bucket, self._k(key),
            ExtraArgs={"ServerSideEncryption": "AES256"},
        )

    def stream(self, key):
        body = self.client.get_object(Bucket=self.bucket, Key=self._k(key))["Body"]
        yield from body.iter_chunks(CHUNK)

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=self._k(key))

    def healthy(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False


def make_storage(cfg):
    if cfg["STORAGE_BACKEND"] == "s3":
        return S3Storage(cfg["S3_BUCKET"], cfg["AWS_REGION"])
    return LocalStorage(cfg["UPLOAD_DIR"])
