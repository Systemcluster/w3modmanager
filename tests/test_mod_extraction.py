"""
Test cases for mod extraction
"""

from .framework import *

from w3modmanager.core.model import *
from w3modmanager.domain.mod.mod import *
from w3modmanager.util.util import *


@pytest.mark.asyncio
async def test_mod_extract_normal(mockdata: Path) -> None:
    archive = mockdata.joinpath('mods/mod-normal.zip')
    source = await extractMod(archive)
    mods = Mod.fromDirectory(source)
    assert len(mods) == 1
    mod = mods[0]
    assert mod.package == 'normal'
    assert mod.filename == 'modNormal'
    assert mod.contentFiles == ['content/blob0.bundle', 'content/metadata.store']


@pytest.mark.asyncio
async def test_mod_extract_long_name(mockdata: Path) -> None:
    archive = mockdata.joinpath('mods/mod-with-long-name.zip')
    source = await extractMod(archive)
    mods = Mod.fromDirectory(source)
    assert len(mods) == 1
    mod = mods[0]
    assert mod.package == 'with long name'
    assert mod.filename == 'mod000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'  # noqa
    assert mod.contentFiles == ['content/blob0.bundle', 'content/metadata.store']
