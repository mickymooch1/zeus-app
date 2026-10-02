"""Website builds go under zeus_agent._PROJECTS_ROOT, which tests point at a temp
dir (conftest.py). Guards against the leak where every full run wrote build files
into C:\\data\\projects (the Windows path of the production default /data/projects)."""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")

import zeus_agent  # noqa: E402

_SRC = (pathlib.Path(__file__).parent.parent / "zeus_agent.py").read_text(encoding="utf-8")


def test_production_default_is_unchanged():
    assert 'os.environ.get("ZEUS_PROJECTS_ROOT", "/data/projects")' in _SRC


def test_tests_build_into_a_temp_dir_not_data():
    root = pathlib.Path(zeus_agent._PROJECTS_ROOT).resolve()
    assert root == pathlib.Path(os.environ["ZEUS_PROJECTS_ROOT"]).resolve()
    assert "zeus-test-projects-" in root.name
    assert not str(root).replace("\\", "/").lower().endswith("/data/projects")


def test_build_paths_no_longer_hard_code_data_projects():
    assert 'f"/data/projects/{site_name}"' not in _SRC
    assert 'f"/data/projects/{project_folder}"' not in _SRC
