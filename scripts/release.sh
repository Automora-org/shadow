#!/usr/bin/env bash
# Bump version, commit ALL changes, tag, and push a clean release.
# Usage: ./scripts/release.sh 1.1.1
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <version>   example: $0 1.1.1" >&2
  exit 1
fi

VERSION="${1#v}"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.]+)?$ ]]; then
  echo "Invalid version: $VERSION" >&2
  exit 1
fi
TAG="v${VERSION}"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean. Commit or stash first, or include everything now." >&2
  echo "This script will commit ALL current changes as the release." >&2
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]] || true; then
  :
fi

python - <<PY
from pathlib import Path
import re

version = "${VERSION}"

pyproject = Path("pyproject.toml")
text = pyproject.read_text(encoding="utf-8")
updated, n = re.subn(r'(?m)^version\s*=\s*"[^"]*"', f'version = "{version}"', text, count=1)
if n != 1:
    raise SystemExit("Failed to update pyproject.toml version")
pyproject.write_text(updated, encoding="utf-8")

Path("shadow/__init__.py").write_text(
    '"""Shadow — freeze observer captures and block a process network."""\n\n'
    f'__version__ = "{version}"\n',
    encoding="utf-8",
)
print(f"version files -> {version}")
PY

uv lock
uv sync --group dev >/dev/null

git add -A
if [[ -z "$(git status --porcelain)" ]]; then
  echo "Nothing to commit; creating tag on current HEAD."
else
  git commit -m "$(cat <<EOF
Release Shadow ${VERSION}.

Include all pending project changes in this version tag.
EOF
)"
fi

# Fail if anything is still dirty after commit.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing to tag: working tree still dirty after commit." >&2
  git status --porcelain >&2
  exit 1
fi

git tag -a "$TAG" -m "Shadow ${VERSION}"
git push origin HEAD
git push origin "$TAG"

echo
echo "Released ${TAG}"
echo "GitHub Actions will build and publish the installer."
echo "Working tree is clean."
