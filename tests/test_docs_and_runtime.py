import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]


def test_auto_toss_runtime_directory_is_git_ignored():
    result = subprocess.run(
        ["git", "check-ignore", ".auto_toss/"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
