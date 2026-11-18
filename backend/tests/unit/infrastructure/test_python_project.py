from pathlib import Path

from app.infrastructure.sandbox.python_project import (
    clean_spec,
    collect_requirement_specs,
    detect_python_project,
)


def test_detects_a_root_project(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("")
    assert detect_python_project(tmp_path) == "."


def test_detects_a_monorepo_subfolder(tmp_path: Path) -> None:
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "package.json").write_text("{}")
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "pyproject.toml").write_text("")
    assert detect_python_project(tmp_path) == "backend"


def test_requirements_are_filtered(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text(
        "# comment\nrequests>=2.0  # http\n-r other.txt\n--index-url http://evil\n"
        "git+https://x/y.git\nfoo @ https://x/foo.whl\npytest==8.0.0\n"
    )
    assert collect_requirement_specs(tmp_path) == ("requests>=2.0", "pytest==8.0.0")


def test_pyproject_dependencies_and_dev_extras(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n'
        'dependencies = ["fastapi>=0.115", "uvicorn[standard]>=0.30"]\n'
        "[project.optional-dependencies]\n"
        'dev = ["pytest>=8.0"]\ndocs = ["sphinx"]\n'
    )
    assert collect_requirement_specs(tmp_path) == (
        "fastapi>=0.115",
        "uvicorn[standard]>=0.30",
        "pytest>=8.0",
    )


def test_option_injection_is_rejected() -> None:
    assert clean_spec("--index-url=http://evil") is None
    assert clean_spec("-e .") is None
    assert clean_spec("requests>=2.0") == "requests>=2.0"
