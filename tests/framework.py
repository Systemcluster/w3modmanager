"""
Framework for test cases
"""

from shutil import rmtree, copytree
from pathlib import Path
from typing import Generator
import sys

import pytest


_root = Path(__file__).parent.parent.resolve()
_mockdata = _root.joinpath('mockdata').resolve(strict=True)

sys.path.append(str(_root))


@pytest.fixture(scope='function')
def mockdata() -> Generator:
    import tempfile
    tempdir = tempfile.mkdtemp()
    copytree(_mockdata, tempdir, dirs_exist_ok=True)
    yield Path(tempdir)
    rmtree(tempdir)
