from app.infrastructure.github.diff_parser import commentable_lines, parse_files

PATCH = "@@ -1,3 +1,4 @@\n line1\n-old\n+new\n+added\n line4"
TWO_HUNKS = "@@ -1,2 +1,2 @@\n a\n+b\n@@ -10,2 +11,3 @@\n c\n+d\n e"


def test_commentable_lines_single_hunk() -> None:
    assert commentable_lines(PATCH) == {1, 2, 3, 4}


def test_commentable_lines_multiple_hunks() -> None:
    assert commentable_lines(TWO_HUNKS) == {1, 2, 11, 12, 13}


def test_no_patch_has_no_lines() -> None:
    assert commentable_lines(None) == set()
    assert commentable_lines("") == set()


def test_deleted_only_lines_are_not_commentable() -> None:
    assert commentable_lines("@@ -1,2 +1 @@\n-gone\n kept") == {1}


def test_parse_files_maps_fields() -> None:
    files = parse_files(
        [
            {
                "filename": "a.py",
                "status": "modified",
                "additions": 3,
                "deletions": 1,
                "patch": "x",
            },
            {"filename": "b.png", "status": "added", "additions": 0, "deletions": 0},
        ]
    )
    assert [f.path for f in files] == ["a.py", "b.png"]
    assert files[0].changes == 4
    assert files[1].patch is None
