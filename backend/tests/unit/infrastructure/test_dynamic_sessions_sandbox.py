import io
import tarfile
from pathlib import Path

import httpx
import pytest

from app.application.ports.sandbox_port import (
    SandboxError,
    Workspace,
)
from app.infrastructure.sandbox.dynamic_sessions_sandbox import (
    DynamicSessionsConfig,
    DynamicSessionsSandbox,
    _tar_directory,
)


# -- fixtures --------------------------------------------------------------


@pytest.fixture
def config() -> DynamicSessionsConfig:
    return DynamicSessionsConfig(
        pool_endpoint="https://pool.example.com",
        api_key="test-key",
        max_session_seconds=60,
        max_concurrency=2,
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    src = tmp_path / "source"
    src.mkdir()
    (src / "hello.py").write_text("print('hello')")
    deps = tmp_path / "deps"
    deps.mkdir()
    return Workspace(source=src, deps=deps)


# -- DynamicSessionsConfig tests ------------------------------------------


def test_config_is_configured_when_endpoint_set() -> None:
    cfg = DynamicSessionsConfig(pool_endpoint="https://x.com")
    assert cfg.is_configured is True


def test_config_is_not_configured_when_endpoint_empty() -> None:
    cfg = DynamicSessionsConfig(pool_endpoint="")
    assert cfg.is_configured is False


def test_config_defaults() -> None:
    cfg = DynamicSessionsConfig()
    assert cfg.max_session_seconds == 300
    assert cfg.max_concurrency == 2
    assert cfg.api_key == ""
    assert cfg.extra_headers == {}


# -- _tar_directory --------------------------------------------------------


def test_tar_directory_creates_valid_archive(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello")
    sub = src / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("world")

    data = _tar_directory(src)
    assert len(data) > 0

    with tarfile.open(
        fileobj=io.BytesIO(data), mode="r:gz"
    ) as tar:
        names = sorted(tar.getnames())
        assert "./a.txt" in names or "a.txt" in names
        found_b = any("b.txt" in n for n in names)
        assert found_b


# -- constructor -----------------------------------------------------------


def test_raises_when_not_configured() -> None:
    cfg = DynamicSessionsConfig(pool_endpoint="")
    with pytest.raises(SandboxError, match="not configured"):
        DynamicSessionsSandbox(cfg)


def test_creates_successfully_when_configured(
    config: DynamicSessionsConfig,
) -> None:
    sandbox = DynamicSessionsSandbox(config)
    assert sandbox is not None


# -- URL building ----------------------------------------------------------


def test_url_includes_session_id_and_api_version(
    config: DynamicSessionsConfig,
) -> None:
    sandbox = DynamicSessionsSandbox(config)
    url = sandbox._url("/code/execute", "abc123")
    assert "identifier=abc123" in url
    assert "api-version=" in url
    assert url.startswith(
        "https://pool.example.com/code/execute"
    )


# -- run() with mocked HTTP -----------------------------------------------


def _mock_response(
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    status: str = "Succeeded",
) -> httpx.Response:
    """Build a fake httpx.Response for Dynamic Sessions."""
    body = {
        "properties": {
            "stdout": stdout,
            "stderr": stderr,
            "exitCode": exit_code,
            "status": status,
        }
    }
    return httpx.Response(
        200,
        json=body,
        request=httpx.Request("POST", "https://x.com"),
    )


async def test_run_success(
    config: DynamicSessionsConfig,
    workspace: Workspace,
) -> None:
    sandbox = DynamicSessionsSandbox(config)

    responses = [
        _mock_response(stdout="uploaded"),  # source upload
        _mock_response(stdout="uploaded"),  # deps upload
        _mock_response(
            stdout="hello\n", exit_code=0
        ),  # execution
    ]
    call_count = 0

    async def mock_post(url, **kwargs):
        nonlocal call_count
        resp = responses[call_count]
        call_count += 1
        return resp

    sandbox._client.post = mock_post  # type: ignore[assignment]

    result = await sandbox.run(
        workspace, ["python", "hello.py"]
    )

    assert result.exit_code == 0
    assert result.stdout == "hello\n"
    assert result.timed_out is False
    assert result.duration_seconds >= 0
    assert call_count == 3


async def test_run_nonzero_exit(
    config: DynamicSessionsConfig,
    workspace: Workspace,
) -> None:
    sandbox = DynamicSessionsSandbox(config)

    responses = [
        _mock_response(stdout="uploaded"),
        _mock_response(stdout="uploaded"),
        _mock_response(
            stderr="error!", exit_code=1
        ),
    ]
    call_count = 0

    async def mock_post(url, **kwargs):
        nonlocal call_count
        resp = responses[call_count]
        call_count += 1
        return resp

    sandbox._client.post = mock_post  # type: ignore[assignment]

    result = await sandbox.run(
        workspace, ["python", "-c", "raise ValueError"]
    )

    assert result.exit_code == 1
    assert "error!" in result.stderr


async def test_run_timeout(
    config: DynamicSessionsConfig,
    workspace: Workspace,
) -> None:
    sandbox = DynamicSessionsSandbox(config)

    async def mock_post(url, **kwargs):
        raise httpx.ReadTimeout("timed out")

    sandbox._client.post = mock_post  # type: ignore[assignment]

    result = await sandbox.run(
        workspace,
        ["sleep", "999"],
        timeout_seconds=1,
    )

    assert result.timed_out is True
    assert result.exit_code == -1


async def test_run_http_status_error(
    config: DynamicSessionsConfig,
    workspace: Workspace,
) -> None:
    sandbox = DynamicSessionsSandbox(config)

    async def mock_post(url, **kwargs):
        resp = httpx.Response(
            500,
            text="internal error",
            request=httpx.Request("POST", url),
        )
        resp.raise_for_status()

    sandbox._client.post = mock_post  # type: ignore[assignment]

    with pytest.raises(SandboxError, match="API error"):
        await sandbox.run(workspace, ["echo", "hi"])


async def test_run_connection_error(
    config: DynamicSessionsConfig,
    workspace: Workspace,
) -> None:
    sandbox = DynamicSessionsSandbox(config)

    async def mock_post(url, **kwargs):
        raise httpx.ConnectError("refused")

    sandbox._client.post = mock_post  # type: ignore[assignment]

    with pytest.raises(
        SandboxError, match="connection error"
    ):
        await sandbox.run(workspace, ["echo", "hi"])


async def test_run_truncates_long_output(
    config: DynamicSessionsConfig,
    workspace: Workspace,
) -> None:
    sandbox = DynamicSessionsSandbox(config)
    long_output = "x" * 6_000_000

    responses = [
        _mock_response(stdout="uploaded"),
        _mock_response(stdout="uploaded"),
        _mock_response(stdout=long_output, exit_code=0),
    ]
    call_count = 0

    async def mock_post(url, **kwargs):
        nonlocal call_count
        resp = responses[call_count]
        call_count += 1
        return resp

    sandbox._client.post = mock_post  # type: ignore[assignment]

    result = await sandbox.run(
        workspace, ["python", "-c", "print('x'*6_000_000)"]
    )

    assert result.truncated is True
    assert len(result.stdout) == 5_000_000


async def test_run_uses_custom_workdir_and_env(
    config: DynamicSessionsConfig,
    workspace: Workspace,
) -> None:
    sandbox = DynamicSessionsSandbox(config)
    captured_bodies: list[dict] = []

    responses = [
        _mock_response(stdout="uploaded"),
        _mock_response(stdout="uploaded"),
        _mock_response(stdout="ok", exit_code=0),
    ]
    call_count = 0

    async def mock_post(url, **kwargs):
        nonlocal call_count
        captured_bodies.append(kwargs.get("json", {}))
        resp = responses[call_count]
        call_count += 1
        return resp

    sandbox._client.post = mock_post  # type: ignore[assignment]

    await sandbox.run(
        workspace,
        ["ruff", "check", "."],
        workdir="backend",
        env={"PYTHONPATH": "/deps"},
    )

    # The execution body (3rd call) should embed the
    # workdir and env in the code template.
    exec_body = captured_bodies[2]
    code = exec_body["properties"]["code"]
    assert "/mnt/user/source/backend" in code
    assert "PYTHONPATH" in code


# -- aclose ----------------------------------------------------------------


async def test_aclose(
    config: DynamicSessionsConfig,
) -> None:
    sandbox = DynamicSessionsSandbox(config)
    await sandbox.aclose()
    # Should not raise.


# -- _build_sandbox integration tests -------------------------------------


def test_build_sandbox_returns_docker_by_default() -> None:
    from app.core.config import Settings
    from app.core.container import _build_sandbox

    settings = Settings(
        sandbox_enabled=True,
        sandbox_backend="docker",
    )
    sandbox = _build_sandbox(settings)
    from app.infrastructure.sandbox.docker_sandbox import (
        DockerSandbox,
    )

    assert isinstance(sandbox, DockerSandbox)


def test_build_sandbox_falls_back_when_no_endpoint() -> None:
    from app.core.config import Settings
    from app.core.container import _build_sandbox

    settings = Settings(
        sandbox_enabled=True,
        sandbox_backend="dynamic_sessions",
        dynamic_sessions_pool_endpoint="",
    )
    sandbox = _build_sandbox(settings)
    from app.infrastructure.sandbox.docker_sandbox import (
        DockerSandbox,
    )

    assert isinstance(sandbox, DockerSandbox)


def test_build_sandbox_returns_dynamic_sessions() -> None:
    from app.core.config import Settings
    from app.core.container import _build_sandbox

    settings = Settings(
        sandbox_enabled=True,
        sandbox_backend="dynamic_sessions",
        dynamic_sessions_pool_endpoint="https://pool.test",
        dynamic_sessions_api_key="key123",
    )
    sandbox = _build_sandbox(settings)
    assert isinstance(sandbox, DynamicSessionsSandbox)
