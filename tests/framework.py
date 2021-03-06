"""
Framework for test cases
"""

from shutil import rmtree
from distutils.dir_util import copy_tree
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
    copy_tree(str(_mockdata), tempdir)
    yield Path(tempdir)
    rmtree(tempdir)
