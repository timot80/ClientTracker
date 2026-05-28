from __future__ import annotations

import re

from ap_filesystem_audit.models import APFilesystemRow, APFilesystemSnapshot


HEADER_RE = re.compile(r"^Filesystem\s+Size\s+Used\s+Available\s+Use%\s+Mounted\s+on$")
PROMPT_RE = re.compile(r"^[A-Za-z0-9_.:-]+[>#]\s*$")
FS_ROW_RE = re.compile(
    r"^(?P<filesystem>\S+)\s+"
    r"(?P<size>\S+)\s+"
    r"(?P<used>\S+)\s+"
    r"(?P<available>\S+)\s+"
    r"(?P<used_percent>\d+)%\s+"
    r"(?P<mount>\S+)$"
)


def parse_filesystems(output: str) -> APFilesystemSnapshot:
    rows: list[APFilesystemRow] = []
    warnings: list[str] = []
    in_table = False

    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or PROMPT_RE.match(stripped):
            continue
        if HEADER_RE.match(stripped):
            in_table = True
            continue
        if not in_table:
            continue

        match = FS_ROW_RE.match(stripped)
        if match:
            rows.append(
                APFilesystemRow(
                    filesystem=match.group("filesystem"),
                    size=match.group("size"),
                    used=match.group("used"),
                    available=match.group("available"),
                    used_percent=int(match.group("used_percent")),
                    mount=match.group("mount"),
                )
            )
            continue
        warnings.append(f"Malformed filesystem row: {stripped}")

    return APFilesystemSnapshot(rows=rows, parser_warnings=warnings)
