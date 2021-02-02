"""
Test cases for mod detection and name formatting

Bin file parsing not part of this test package.
"""

from .framework import *

from w3modmanager.core.model import *
from w3modmanager.domain.mod.mod import *


@pytest.mark.asyncio
async def test_mod_normal(mockdata: Path) -> None:
    source = mockdata.joinpath('mods/normal')
    mods = await Mod.fromDirectory(source)
    assert len(mods) == 1
    mod = mods[0]
    assert mod.package == 'normal'
    assert mod.filename == 'modNormal'
    assert mod.datatype == 'mod'
    assert mod.source == source.joinpath('modNormal')
    assert mod.contentFiles == ['content/blob0.bundle', 'content/metadata.store']
    assert mod.scriptFiles == []
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []


@pytest.mark.asyncio
async def test_mod_direct(mockdata: Path) -> None:
    source = mockdata.joinpath('mods/mod-direct')
    mods = await Mod.fromDirectory(source)
    assert len(mods) == 1
    mod = mods[0]
    assert mod.package == 'direct'
    assert mod.filename == 'modDirect'
    assert mod.datatype == 'mod'
    assert mod.source == source
    assert mod.contentFiles == ['content/blob0.bundle', 'content/metadata.store']
    assert mod.scriptFiles == []
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []


@pytest.mark.asyncio
async def test_mod_contains_no_dlc(mockdata: Path) -> None:
    source = mockdata.joinpath('mods/mod-without-dlc')
    mods = await Mod.fromDirectory(source)
    assert len(mods) == 1
    mod = mods[0]
    assert mod.package == 'without dlc'
    assert mod.filename == 'modWithoutDlc'
    assert mod.datatype == 'mod'
    assert mod.source == source
    assert mod.contentFiles == [
        'content/blob0.bundle',
        'content/metadata.store',
        'content/dlc/EP1/content/de.w3strings',
        'content/dlc/EP1/content/en.w3strings']
    assert mod.scriptFiles == []
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []


@pytest.mark.asyncio
async def test_mod_dlc(mockdata: Path) -> None:
    source = mockdata.joinpath('mods/mod-with-dlc')
    mods = await Mod.fromDirectory(source)
    assert len(mods) == 2
    mod = mods[0]
    assert mod.package == 'with dlc'
    assert mod.filename == 'mod-dlc'
    assert mod.datatype == 'dlc'
    assert mod.source == source.joinpath('dlc/mod-dlc')
    assert mod.contentFiles == ['content/blob0.bundle', 'content/metadata.store']
    assert mod.scriptFiles == []
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []
    mod = mods[1]
    assert mod.package == 'with dlc'
    assert mod.filename == 'modDlc'
    assert mod.datatype == 'mod'
    assert mod.source == source.joinpath('mods/mod-dlc')
    assert mod.contentFiles == ['content/blob0.bundle', 'content/metadata.store']
    assert mod.scriptFiles == []
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []


@pytest.mark.asyncio
async def test_mod_valid(mockdata: Path) -> None:
    source = mockdata.joinpath('mods/valid')
    mods = await Mod.fromDirectory(source)
    assert len(mods) == 4
    mod = mods[0]
    assert mod.package == 'valid'
    assert mod.filename == 'dlcTestmod'
    assert mod.datatype == 'dlc'
    assert mod.source == source.joinpath('dlcTestmod')
    assert mod.contentFiles == [
        'content/blob0.bundle', 'content/metadata.store']
    assert mod.scriptFiles == []
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []
    mod = mods[1]
    assert mod.package == 'valid'
    assert mod.filename == 'modTestmod'
    assert mod.datatype == 'mod'
    assert mod.source == source.joinpath('MODTestmod')
    assert mod.contentFiles == ['content/blob0.bundle', 'content/metadata.store']
    assert mod.scriptFiles == ['content/scripts/game/r4game.ws']
    assert mod.binFiles == []
    assert mod.menuFiles == [
        'modTest.xml (bin/config/r4game/user_config_matrix/pc/modTest.xml)',
        'bin/config/r4game/user_config_matrix/pc/input.xml',
        'bin/config/r4game/user_config_matrix/pc/modTestConfig.xml',
        'bin/config/r4game/user_config_matrix/pc/rendering.xml']
    assert mod.settings[0].source == Path('validuser.settings.part.txt')
    assert mod.inputs[0].source == Path('inputsettings.txt')
    mod = mods[2]
    assert mod.package == 'valid'
    assert mod.filename == 'modTestmodExtra'
    assert mod.datatype == 'mod'
    assert mod.source == source.joinpath('mods/modTestmodExtra')
    assert mod.contentFiles == [
        'content/blob0.bundle', 'content/metadata.store']
    assert mod.scriptFiles == []
    assert mod.binFiles == []
    assert mod.menuFiles == ['inputxml.txt (bin/config/r4game/user_config_matrix/pc/input.xml)']
    assert mod.settings == []
    assert mod.inputs == []
    mod = mods[3]
    assert mod.package == 'valid'
    assert mod.filename == 'binValid'
    assert mod.datatype == 'bin'
    assert mod.source == source
    assert mod.contentFiles == []
    assert mod.scriptFiles == []
    assert mod.binFiles == ['bin/config/base/localization.ini']
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []


@pytest.mark.asyncio
async def test_mod_weird(mockdata: Path) -> None:
    source = mockdata.joinpath('mods/weird')
    mods = await Mod.fromDirectory(source)
    assert len(mods) == 3
    mod = mods[0]
    assert mod.package == 'weird'
    assert mod.filename == 'modFoo'
    assert mod.datatype == 'udf'
    assert mod.source == source.joinpath('foo 1.2')
    assert mod.contentFiles == ['content/placeholder.txt']
    assert mod.scriptFiles == []
    assert mod.binFiles == ['bin/config/performance.xml']
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []
    mod = mods[1]
    assert mod.package == 'weird'
    assert mod.filename == 'modFooExtras'
    assert mod.datatype == 'udf'
    assert mod.source == source.joinpath('foo extras')
    assert mod.contentFiles == ['content/placeholder.txt']
    assert mod.scriptFiles == []
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []
    mod = mods[2]
    assert mod.package == 'weird'
    assert mod.filename == 'binFoo12Menus'
    assert mod.datatype == 'bin'
    assert mod.source == source.joinpath('foo 1.2 menus')
    assert mod.contentFiles == []
    assert mod.scriptFiles == []
    assert mod.binFiles == ['bin/config/performance.xml']
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []


@pytest.mark.asyncio
async def test_patch(mockdata: Path) -> None:
    source = mockdata.joinpath('mods/patch')
    mods = await Mod.fromDirectory(source)
    assert len(mods) == 2
    mod = mods[0]
    assert mod.package == 'patch'
    assert mod.filename == 'mod0000____CompilationTrigger'
    assert mod.datatype == 'mod'
    assert mod.contentFiles == []
    assert mod.scriptFiles == ['content/scripts/compilationTrigger.ws']
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []
    mod = mods[1]
    assert mod.package == 'patch'
    assert mod.filename == 'patCh'
    assert mod.datatype == 'pat'
    assert mod.contentFiles == []
    assert mod.scriptFiles == ['content/content0/scripts/game/r4game.ws']
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []


@pytest.mark.asyncio
async def test_only_dlc(mockdata: Path) -> None:
    source = mockdata.joinpath('mods/only-dlc')
    mods = await Mod.fromDirectory(source)
    assert len(mods) == 1
    mod = mods[0]
    assert mod.package == 'only dlc'
    assert mod.filename == 'dlc__only'
    assert mod.datatype == 'dlc'
    assert mod.contentFiles == ['content/blob0.bundle', 'content/metadata.store']
    assert mod.scriptFiles == []
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []


@pytest.mark.asyncio
async def test_mod_with_split_bins(mockdata: Path) -> None:
    source = mockdata.joinpath('mods/mod-with-split-bins')
    mods = await Mod.fromDirectory(source)
    assert len(mods) == 1
    mod = mods[0]
    assert mod.package == 'with split bins'
    assert mod.filename == 'binWithSplitBins'
    assert mod.datatype == 'bin'
    assert mod.contentFiles == []
    assert mod.scriptFiles == []
    assert mod.binFiles == [
        'a/bin/config/graphics.xml (bin/config/graphics.xml)',
        'b/bin/config/performance.xml (bin/config/performance.xml)']
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []


@pytest.mark.asyncio
async def test_mod_dlc_same_name(mockdata: Path) -> None:
    source = mockdata.joinpath('mods/mod-with-dlc-same-name')
    mods = await Mod.fromDirectory(source)
    assert len(mods) == 2
    mod = mods[0]
    assert mod.package == 'with dlc same name'
    assert mod.filename == 'modDlc'
    assert mod.datatype == 'dlc'
    assert mod.source == source.joinpath('dlc/modDlc')
    assert mod.contentFiles == ['content/blob0.bundle', 'content/metadata.store']
    assert mod.scriptFiles == []
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []
    mod = mods[1]
    assert mod.package == 'with dlc same name'
    assert mod.filename == 'modDlc'
    assert mod.datatype == 'mod'
    assert mod.source == source.joinpath('mods/modDlc')
    assert mod.contentFiles == ['content/blob0.bundle', 'content/metadata.store']
    assert mod.scriptFiles == []
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == []


@pytest.mark.asyncio
async def test_mod_with_inputs(mockdata: Path) -> None:
    source = mockdata.joinpath('mods/mod-with-inputs')
    mods = await Mod.fromDirectory(source)
    assert len(mods) == 1
    mod = mods[0]
    assert mod.package == 'with inputs'
    assert mod.filename == 'modWithInputs'
    assert mod.datatype == 'mod'
    assert mod.source == source
    assert mod.contentFiles == ['content/blob0.bundle', 'content/metadata.store']
    assert mod.scriptFiles == []
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == [InputSettings(Path('input.settings.part.txt'), '''
        [Test]
        IK_0=(Action=TEST_0)
        IK_1=(Action=TEST_1)
        IK_Tab=(Action=TEST_2)
    ''')]
    assert len(mod.inputs[0]) == 3


@pytest.mark.asyncio
async def test_mod_with_inputs_readme(mockdata: Path) -> None:
    source = mockdata.joinpath('mods/mod-with-inputs-readme')
    mods = await Mod.fromDirectory(source)
    assert len(mods) == 1
    mod = mods[0]
    assert mod.package == 'with inputs readme'
    assert mod.filename == 'modWithInputsReadme'
    assert mod.datatype == 'mod'
    assert mod.source == source
    assert mod.contentFiles == ['content/blob0.bundle', 'content/metadata.store']
    assert mod.scriptFiles == []
    assert mod.binFiles == []
    assert mod.menuFiles == []
    assert mod.settings == []
    assert mod.inputs == [InputSettings(Path('input.settings.readme.txt'), '''
        [Test]
        IK_0=(Action=TEST_0)
        IK_1=(Action=TEST_1)
        IK_Tab=(Action=TEST_2)
        [Exploration]
        IK_Z=(Action=OpenTestMenu)
    ''')]
    assert len(mod.inputs[0]) == 4
