import subprocess
from pathlib import Path


def test_project_script_is_available_through_uv_run():
    project_root = Path(__file__).parents[1]

    result = subprocess.run(
        ["uv", "run", "auto-toss", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage: auto-toss" in result.stdout
