import re

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def commentable_lines(patch: str | None) -> set[int]:
    """Line numbers (new side) that GitHub accepts for inline review comments."""
    lines: set[int] = set()
    if not patch:
        return lines
    current = 0
    in_hunk = False
    for raw in patch.splitlines():
        match = _HUNK.match(raw)
        if match:
            current = int(match.group(1))
            in_hunk = True
            continue
        if in_hunk and raw[:1] in ("+", " "):
            lines.add(current)
            current += 1
    return lines


def annotate_patch(patch: str | None) -> str:
    """Prefix each visible line with its new-file line number so an LLM can cite lines."""
    if not patch:
        return ""
    out: list[str] = []
    current = 0
    in_hunk = False
    for raw in patch.splitlines():
        match = _HUNK.match(raw)
        if match:
            current = int(match.group(1))
            in_hunk = True
            out.append(raw)
            continue
        if not in_hunk:
            continue
        marker, text = raw[:1], raw[1:]
        if marker == "+":
            out.append(f"{current:>5} +{text}")
            current += 1
        elif marker == " ":
            out.append(f"{current:>5}  {text}")
            current += 1
        elif marker == "-":
            out.append(f"{'':>5} -{text}")
    return "\n".join(out)