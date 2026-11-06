#!/usr/bin/env python3
"""
Version 7.2 INI hash-only fixer for Vesna and Odette.

Scans only the directory containing this script and its subdirectories.
Creates <original filename>.v7.2.bak before the first modification.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

BACKUP_SUFFIX = ".v7.2.bak"

# Exact old -> new hash pairs from the supplied screenshots.
VESNA_EXACT = {
    "body": ("291f5ac5", "3f608555"),
    "bangs": ("965a2e11", "bb8a98b9"),
}
VESNA_BLEND_OLD = "00ca49fb"
VESNA_BLEND_NEW = "74169e10"

# Optional Vesna wing hashes from the update screenshot.
# Only applied inside INI sections whose names contain "wing".
VESNA_WING_EXACT = {
    "0d7633ec": "079f8754",
    "aeeabed4": "64bc63ee",
}

# BellaBell's other listed hashes are intentionally NOT update targets:
# position edef98b6, texcoord 141809db, and IB c98648d6.
ODETTE_EXACT = {
    "position": ("1ef5195e", "6e92bf69"),
    "blend": ("0ea973a0", "c4d1b435"),
    "bodytexcoord": ("b7399f02", "ed9888ab"),
    "bodyvertexlimitraise": ("c82fb483", "919d78ee"),
    "ib": ("bf1830b6", "f5bcaac2"),
}

SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(?:[;#].*)?$")
HASH_RE = re.compile(r"^(\s*hash\s*=\s*)([0-9a-fA-F]+)(.*)$", re.IGNORECASE)


# Hash-only replacement table. No INI section names are inspected.
# Every exact old hash found on a `hash = ...` line is replaced wherever it occurs.
HASH_REPLACEMENTS = {
    # Vesna
    "291f5ac5": "3f608555",  # body
    "965a2e11": "bb8a98b9",  # bangs
    "00ca49fb": "74169e10",  # blend
    "0d7633ec": "079f8754",  # optional wings supplement
    "aeeabed4": "64bc63ee",  # optional wings supplement

    # Odette
    "1ef5195e": "6e92bf69",  # position
    "0ea973a0": "c4d1b435",  # blend
    "b7399f02": "ed9888ab",  # body texcoord
    "c82fb483": "919d78ee",  # body vertex limit raise
    "bf1830b6": "f5bcaac2",  # IB and body mesh IBs
}

SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(?:[;#].*)?$")
HASH_RE = re.compile(r"^(\s*hash\s*=\s*)([0-9a-fA-F]+)(.*)$", re.IGNORECASE)


def is_disabled_ini(path: Path) -> bool:
    """True when the INI filename (without extension) contains DISABLED."""
    return "DISABLED" in path.stem.upper()


def fix_ini(path: Path, root: Path) -> tuple[bool, list[str]]:
    raw = path.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")

    try:
        text = raw.decode("utf-8-sig")
        encoding = "utf-8"
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
        encoding = "cp1252"

    lines = text.splitlines(keepends=True)
    edits: list[tuple[int, str, str]] = []

    # Match solely on the hash value. Section names and mod names are ignored.
    for index, line in enumerate(lines):
        content = line.rstrip("\r\n")
        match = HASH_RE.match(content)
        if not match:
            continue

        old_hash = match.group(2).lower()
        new_hash = HASH_REPLACEMENTS.get(old_hash)
        if new_hash and old_hash != new_hash:
            edits.append((index, old_hash, new_hash))

    if not edits:
        return False, []

    messages: list[str] = []
    for index, old_hash, new_hash in edits:
        content = lines[index].rstrip("\r\n")
        ending = lines[index][len(content):]
        match = HASH_RE.match(content)
        if match:
            lines[index] = f"{match.group(1)}{new_hash}{match.group(3)}{ending}"
            messages.append(
                f"{path.relative_to(root)}: line {index + 1}: "
                f"{old_hash} -> {new_hash}"
            )

    new_text = "".join(lines)
    output = (b"\xef\xbb\xbf" if has_bom else b"") + new_text.encode(encoding)

    backup = path.with_name(path.name + BACKUP_SUFFIX)
    if not backup.exists():
        shutil.copy2(path, backup)
    else:
        messages.append(
            f"{path.relative_to(root)}: existing backup kept unchanged"
        )

    path.write_bytes(output)
    return True, messages


def main() -> None:
    # In a PyInstaller --onefile EXE, __file__ points into the temporary
    # _MEI extraction directory. Use the EXE's actual directory instead.
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent
    else:
        root = Path(__file__).resolve().parent

    print("Version 7.2 - Vesna / Odette INI Hash-Only Fixer")
    print(f"Scan root: {root}")
    print("Only this folder and its subfolders will be scanned.")
    print("For an EXE, this is the folder containing the EXE.")
    print()
    while True:
        answer = input(
            'Process INI files whose filename contains "DISABLED"? [y/n]: '
        ).strip().lower()
        if answer in ("y", "n"):
            break
        print("Please enter y for yes or n for no.")

    include_disabled = answer == "y"
    print(
        'DISABLED files: INCLUDED'
        if include_disabled else
        'DISABLED files: SKIPPED'
    )
    print()

    ini_files = sorted(
        item for item in root.rglob("*")
        if item.is_file()
        and item.suffix.lower() == ".ini"
        and not item.is_symlink()
        and not any(part.startswith(".") for part in item.relative_to(root).parts)
        and (include_disabled or not is_disabled_ini(item))
    )

    changed_count = 0
    messages: list[str] = []

    for ini_path in ini_files:
        try:
            changed, file_messages = fix_ini(ini_path, root)
            if changed:
                changed_count += 1
            messages.extend(file_messages)
        except Exception as exc:
            messages.append(f"ERROR: {ini_path.relative_to(root)}: {exc}")

    if messages:
        print("\n".join(messages))
    else:
        print("No matching old hashes needed changing.")

    print()
    print(f"Finished. Changed {changed_count} INI file(s).")
    print(f"Scanned {len(ini_files)} INI file(s).")
    print(f"Backup suffix: {BACKUP_SUFFIX}")
    input("Press Enter to close...")


if __name__ == "__main__":
    main()
