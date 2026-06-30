"""Deterministic file-tree hashing for golden-master comparison."""
from __future__ import annotations

import hashlib
import json
import os


def hash_tree(root: str) -> dict:
    result: dict[str, str] = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            h = hashlib.sha256()
            with open(full, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            result[rel] = h.hexdigest()
    return dict(sorted(result.items()))


def write_manifest(root: str, manifest_path: str) -> dict:
    manifest = hash_tree(root)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    return manifest


def diff_manifests(a: dict, b: dict) -> list:
    lines: list[str] = []
    for key in sorted(set(a) | set(b)):
        if key not in b:
            lines.append(f"REMOVED: {key}")
        elif key not in a:
            lines.append(f"ADDED:   {key}")
        elif a[key] != b[key]:
            lines.append(f"CHANGED: {key}")
    return lines
