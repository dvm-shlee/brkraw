import os
import shutil
import sys
import tempfile
from pathlib import Path
import pytest

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[1]
SRC_DIR = REPO_ROOT / "src"

# The developer's real home folder, read once before any test changes HOME.
# Tests use it only to assert that nothing points there.
REAL_HOME = Path.home()

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tests.agent_fixtures import find_approved_zips, fixtures_dir  # noqa: E402
from tests.helpers import KEEP_ENV, isolate_brkraw_env  # noqa: E402


def pytest_configure(config):
    # Before collection: no brkraw session variables, and a config home that is
    # never the developer's ~/.brkraw, in case anything reads config at import.
    for key in list(os.environ):
        if key.startswith("BRKRAW_") and key not in KEEP_ENV:
            del os.environ[key]
    os.environ["BRKRAW_CONFIG_HOME"] = os.path.join(tempfile.gettempdir(), "brkraw-pytest-collection-config")
    config.addinivalue_line(
        "markers",
        "agent_fixtures: uses approved anonymized zips from the agent-fixtures folder (skipped when absent)",
    )


@pytest.fixture(autouse=True)
def _isolated_brkraw_env(tmp_path_factory, monkeypatch):
    """Every test gets its own empty config home and HOME, and no BRKRAW_* session variables.

    Variables a test run sets itself (for example BRKRAW_PATH chosen from
    ParaVision by the CLI) are removed afterwards so they cannot leak into the
    next test; monkeypatch restores the ones it changed.
    """
    isolate_brkraw_env(monkeypatch, tmp_path_factory.mktemp("brkraw-env"))
    before = {k for k in os.environ if k.startswith("BRKRAW_")}
    yield
    for key in [k for k in os.environ if k.startswith("BRKRAW_") and k not in before]:
        del os.environ[key]


@pytest.fixture
def approved_zips(tmp_path):
    """Return a function ``approved_zips(pv)`` -> list of approved zips copied into ``tmp_path``.

    Skips the test (with the reasons) when the folder, README rows or zips are
    missing, not approved, or do not match their SHA-256. Tests never write in
    the agent-fixtures folder itself.
    """

    def _get(pv: str):
        found, reasons = find_approved_zips(fixtures_dir(), pv)
        if not found:
            pytest.skip("no approved agent fixture for {}: {}".format(pv, "; ".join(reasons)))
        dest = tmp_path / "agent-fixtures" / pv
        dest.mkdir(parents=True, exist_ok=True)
        copies = []
        for src in found:
            target = dest / src.name
            shutil.copyfile(src, target)
            copies.append(target)
        return copies

    return _get
