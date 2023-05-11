"""
Framework for test cases
"""

import sys

from collections.abc import Generator
from pathlib import Path
from shutil import copytree, rmtree

import pytest


_root = Path(__file__).parent.parent.resolve()
_mockdata = _root.joinpath('mockdata').resolve(strict=True)

sys.path.append(str(_root))


@pytest.fixture(scope='function')
def mockdata() -> Generator[Path, None, None]:
    import tempfile
    tempdir = tempfile.mkdtemp()
    copytree(_mockdata, tempdir, dirs_exist_ok=True)
    yield Path(tempdir)
    rmtree(tempdir)
