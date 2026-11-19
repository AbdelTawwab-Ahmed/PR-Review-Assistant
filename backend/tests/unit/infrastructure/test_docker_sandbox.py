import os
from pathlib import Path

import pytest

from app.application.ports.sandbox_port import SandboxError, Workspace
from app.infrastructure.sandbox.docker_sandbox import BASE_ENV, DockerSandbox

needs_docker = pytest.mark.skipif(
    not os.environ.get("RUN_DOCKER_TESTS"),
    reason="set RUN_DOCKER_TESTS=1 (needs Docker and the prra-sandbox image)",
)


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    (tmp_path / "src").mkdir()
    (tmp_path / "deps").mkdir()
    (tmp_path / "src" / "hello.py").write_text("print('hello')")
    return Workspace(tmp_path / "src", tmp_path / "deps")


def build(workspace: Workspace, **kwargs) -> list[str]:
    sandbox = DockerSandbox(image="img:1")
    return sandbox.build_command("n", workspace, ["ruff", "check"], **kwargs)


def test_command_is_locked_down(workspace: Workspace) -> None:
    args = build(workspace, workdir="backend", env={"PYTHONPATH": "/deps"})
    assert args[:2] == ["docker", "run"]
    assert args[args.index("--network") + 1] == "none"
    assert args[args.index("--cap-drop") + 1] == "ALL"
    assert "--read-only" in args
    assert "no-new-privileges" in args
    assert f"type=bind,source={workspace.source},target=/src,readonly" in args
    assert f"type=bind,source={workspace.deps},target=/deps,readonly" in args
    assert args[-3:] == ["backend", "ruff", "check"]


def test_only_known_environment_is_passed(workspace: Workspace) -> None:
    args = build(workspace, env={"PYTHONPATH": "/deps"})
    keys = {a.split("=")[0] for i, a in enumerate(args) if args[i - 1] == "--env"}
    assert keys == set(BASE_ENV) | {"PYTHONPATH"}


def test_install_mode_enables_network_and_writable_deps(workspace: Workspace) -> None:
    args = build(workspace, install_mode=True)
    assert args[args.index("--network") + 1] == "bridge"
    assert f"type=bind,source={workspace.deps},target=/deps" in args


def test_bad_environment_names_are_rejected(workspace: Workspace) -> None:
    with pytest.raises(SandboxError):
        build(workspace, env={"BAD KEY": "x"})


def test_working_directory_cannot_escape(workspace: Workspace) -> None:
    with pytest.raises(SandboxError):
        build(workspace, workdir="../etc")


@needs_docker
async def test_code_runs_without_network_or_host_secrets(workspace: Workspace, monkeypatch) -> None:
    monkeypatch.setenv("PRRA_TEST_SECRET", "s3cret")
    sandbox = DockerSandbox(image="prra-sandbox:latest")

    hello = await sandbox.run(workspace, ["python", "hello.py"])
    assert hello.stdout.strip() == "hello"

    env = await sandbox.run(workspace, ["env"])
    assert "s3cret" not in env.stdout

    net = await sandbox.run(
        workspace, ["python", "-c", "import socket; socket.create_connection(('1.1.1.1', 53), 3)"]
    )
    assert net.exit_code != 0


@needs_docker
async def test_source_is_read_only_and_edits_are_discarded(workspace: Workspace) -> None:
    sandbox = DockerSandbox(image="prra-sandbox:latest")
    result = await sandbox.run(workspace, ["sh", "-c", "echo changed > hello.py; touch /src/x"])
    assert result.exit_code != 0
    assert (workspace.source / "hello.py").read_text() == "print('hello')"


@needs_docker
async def test_timeout_kills_the_container(workspace: Workspace) -> None:
    sandbox = DockerSandbox(image="prra-sandbox:latest")
    result = await sandbox.run(workspace, ["sleep", "60"], timeout_seconds=3)
    assert result.timed_out
