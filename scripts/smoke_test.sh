#!/usr/bin/env bash
# End-to-end check of a running CloudVault. Works for local, Docker and EC2.
# Usage: scripts/smoke_test.sh http://localhost        (default http://localhost:5000)
set -euo pipefail
BASE="${1:-http://localhost:5000}"
JAR="$(mktemp)"; trap 'rm -f "$JAR" /tmp/cv_up.txt' EXIT
USER="smoke$RANDOM"; PASS="smokepass123"
ok(){ echo "  PASS  $1"; }; fail(){ echo "  FAIL  $1"; exit 1; }
token(){ curl -s -b "$JAR" -c "$JAR" "$BASE/$1" | grep -o 'name="csrf_token" value="[^"]*"' | head -1 | cut -d'"' -f4; }

echo "Smoke test against $BASE"
curl -sf "$BASE/health" | grep -q '"status":"ok"' && ok "health endpoint" || fail "health endpoint"

T=$(token register)
curl -s -b "$JAR" -c "$JAR" -o /dev/null -d "csrf_token=$T&username=$USER&password=$PASS" "$BASE/register"
T=$(token login)
curl -s -b "$JAR" -c "$JAR" -o /dev/null -d "csrf_token=$T&username=$USER&password=$PASS" "$BASE/login"
curl -s -b "$JAR" "$BASE/dashboard" | grep -q "My files" && ok "register and login" || fail "register and login"

echo "hello from smoke test" > /tmp/cv_up.txt
T=$(token dashboard)
curl -s -b "$JAR" -c "$JAR" -o /dev/null -F "csrf_token=$T" -F "file=@/tmp/cv_up.txt" "$BASE/upload"
curl -s -b "$JAR" "$BASE/dashboard" | grep -q "cv_up.txt" && ok "upload" || fail "upload"

ID=$(curl -s -b "$JAR" "$BASE/dashboard" | grep -o '/files/[0-9]*/download' | head -1 | grep -o '[0-9]*')
[ "$(curl -s -b "$JAR" "$BASE/files/$ID/download")" = "hello from smoke test" ] && ok "download matches" || fail "download"

T=$(token dashboard)
curl -s -b "$JAR" -c "$JAR" -d "csrf_token=$T&hours=1" "$BASE/files/$ID/share" -L | grep -o '/s/[A-Za-z0-9_-]*' | head -1 > /tmp/cv_link.txt
LINK=$(cat /tmp/cv_link.txt); rm -f /tmp/cv_link.txt
[ "$(curl -s "$BASE$LINK/download")" = "hello from smoke test" ] && ok "public share link" || fail "share link"

T=$(token dashboard)
curl -s -b "$JAR" -c "$JAR" -o /dev/null -d "csrf_token=$T" "$BASE/files/$ID/delete"
[ "$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR" "$BASE/files/$ID/download")" = "404" ] && ok "delete" || fail "delete"
echo "All checks passed."
