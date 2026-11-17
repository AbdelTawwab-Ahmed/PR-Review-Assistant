from app.domain.services.diff_lines import annotate_patch


def test_annotate_numbers_new_side_lines() -> None:
    patch = "@@ -1,3 +1,4 @@\n line1\n-old\n+new\n+added\n line4"
    assert annotate_patch(patch).splitlines() == [
        "@@ -1,3 +1,4 @@",
        "    1  line1",
        "      -old",
        "    2 +new",
        "    3 +added",
        "    4  line4",
    ]


def test_second_hunk_restarts_numbering() -> None:
    patch = "@@ -1 +1 @@\n+a\n@@ -20 +30 @@\n+b"
    assert annotate_patch(patch).splitlines()[-1] == "   30 +b"


def test_empty_patch() -> None:
    assert annotate_patch(None) == ""
    assert annotate_patch("") == ""


def test_no_newline_marker_is_skipped() -> None:
    patch = "@@ -1 +1 @@\n-a\n+b\n\\ No newline at end of file"
    assert "No newline" not in annotate_patch(patch)