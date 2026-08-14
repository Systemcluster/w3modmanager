"""
Test cases for mod model behavior
"""

from w3modmanager.core.model import *
from w3modmanager.domain.mod.mod import *

from .framework import *

from typing import Any, cast


def create_model(mockdata: Path) -> Model:
    model = Model(
        mockdata.joinpath('programs'),
        mockdata.joinpath('documents'),
        mockdata.joinpath('cache'),
        ignorelock=True,
    )
    test_model = cast(Any, model)
    test_model._modsSettings.watcher._observer.stop()
    test_model._pool.shutdown(wait=False)
    test_model._pool = None
    return model


def content_files(mod: Mod) -> list[str]:
    return sorted(str(file) for file in mod.contentFiles)


def mod_settings_value(model: Model, section: str, key: str) -> str | None:
    test_model = cast(Any, model)
    return cast(str | None, test_model._modsSettings.getValue(section, key))


def test_verify_paths_are_case_insensitive(mockdata: Path) -> None:
    mockdata.joinpath('programs/content').rename(mockdata.joinpath('programs/CONTENT'))
    mockdata.joinpath('programs/bin').rename(mockdata.joinpath('programs/BIN'))
    mockdata.joinpath('programs/BIN/x64').rename(mockdata.joinpath('programs/BIN/X64'))
    mockdata.joinpath('programs/BIN/X64/witcher3.exe').rename(mockdata.joinpath('programs/BIN/X64/WITCHER3.EXE'))
    mockdata.joinpath('documents/user.settings').rename(mockdata.joinpath('documents/USER.SETTINGS'))
    mockdata.joinpath('documents/input.settings').rename(mockdata.joinpath('documents/INPUT.SETTINGS'))

    assert verifyGamePath(mockdata.joinpath('programs')) == mockdata.joinpath('programs').resolve()
    assert verifyConfigPath(mockdata.joinpath('documents')) == mockdata.joinpath('documents').resolve()


@pytest.mark.asyncio()
async def test_model_add_mod(mockdata: Path) -> None:
    model = create_model(mockdata)
    mods = await Mod.fromDirectory(mockdata.joinpath('mods/mod-direct'))

    await model.add(mods[0])

    mod = model[('modDirect', 'mods')]
    target = mockdata.joinpath('programs/Mods/modDirect')
    assert len(model) == 1
    assert mod.package == 'direct'
    assert mod.filename == 'modDirect'
    assert mod.datatype == 'mod'
    assert mod.installed is True
    assert mod.enabled is True
    assert content_files(mod) == ['content/blob0.bundle', 'content/metadata.store']
    assert target.joinpath('.w3mm').is_file()
    assert target.joinpath('content/blob0.bundle').is_file()
    assert target.joinpath('content/metadata.store').is_file()
    assert mod_settings_value(model, 'modDirect', 'Enabled') == '1'


@pytest.mark.asyncio()
async def test_model_add_dlc(mockdata: Path) -> None:
    model = create_model(mockdata)
    mods = await Mod.fromDirectory(mockdata.joinpath('mods/only-dlc'))

    await model.add(mods[0])

    mod = model[('dlc__only', 'dlc')]
    target = mockdata.joinpath('programs/DLC/dlc__only')
    assert len(model) == 1
    assert mod.package == 'only dlc'
    assert mod.filename == 'dlc__only'
    assert mod.datatype == 'dlc'
    assert mod.installed is True
    assert mod.enabled is True
    assert content_files(mod) == ['content/blob0.bundle', 'content/metadata.store']
    assert target.joinpath('.w3mm').is_file()
    assert target.joinpath('content/blob0.bundle').is_file()
    assert target.joinpath('content/metadata.store').is_file()


@pytest.mark.asyncio()
async def test_model_add_bin_mod(mockdata: Path) -> None:
    model = create_model(mockdata)
    mods = await Mod.fromDirectory(mockdata.joinpath('mods/mod-with-split-bins'))

    await model.add(mods[0])

    mod = model[('binWithSplitBins', 'mods')]
    target = mockdata.joinpath('programs/Mods/binWithSplitBins')
    assert len(model) == 1
    assert mod.package == 'with split bins'
    assert mod.filename == 'binWithSplitBins'
    assert mod.datatype == 'bin'
    assert mod.installed is True
    assert mod.enabled is True
    assert mod.binFiles == [
        'a/bin/config/graphics.xml (bin/config/graphics.xml)',
        'b/bin/config/performance.xml (bin/config/performance.xml)']
    assert target.joinpath('.w3mm').is_file()
    assert target.joinpath('a/bin/config/graphics.xml').is_file()
    assert target.joinpath('b/bin/config/performance.xml').is_file()


@pytest.mark.asyncio()
async def test_model_add_rejects_duplicate_mod(mockdata: Path) -> None:
    model = create_model(mockdata)
    mods = await Mod.fromDirectory(mockdata.joinpath('mods/mod-direct'))

    await model.add(mods[0])
    with pytest.raises(ModExistsError):
        await model.add(mods[0])


@pytest.mark.asyncio()
async def test_model_disable_and_enable_mod(mockdata: Path) -> None:
    model = create_model(mockdata)
    mods = await Mod.fromDirectory(mockdata.joinpath('mods/mod-direct'))
    await model.add(mods[0])

    disabled = await model.disable(('modDirect', 'mods'))

    mod = model[('modDirect', 'mods')]
    assert disabled is True
    assert mod.enabled is False
    assert not mockdata.joinpath('programs/Mods/modDirect').exists()
    assert mockdata.joinpath('programs/Mods/~modDirect').is_dir()
    assert mod_settings_value(model, 'modDirect', 'Enabled') == '0'

    enabled = await model.enable(('modDirect', 'mods'))

    assert enabled is True
    assert mod.enabled is True
    assert mockdata.joinpath('programs/Mods/modDirect').is_dir()
    assert not mockdata.joinpath('programs/Mods/~modDirect').exists()
    assert mod_settings_value(model, 'modDirect', 'Enabled') == '1'


@pytest.mark.asyncio()
async def test_model_remove_mod(mockdata: Path) -> None:
    model = create_model(mockdata)
    mods = await Mod.fromDirectory(mockdata.joinpath('mods/mod-direct'))
    await model.add(mods[0])

    await model.remove(('modDirect', 'mods'))

    assert len(model) == 0
    assert not mockdata.joinpath('programs/Mods/modDirect').exists()
    assert not mockdata.joinpath('programs/Mods/~modDirect').exists()
    with pytest.raises(ModNotFoundError):
        model[('modDirect', 'mods')]
    assert mod_settings_value(model, 'modDirect', 'Enabled') is None


@pytest.mark.asyncio()
async def test_model_load_installed_mod_with_metadata(mockdata: Path) -> None:
    installed_model = create_model(mockdata)
    mods = await Mod.fromDirectory(mockdata.joinpath('mods/mod-direct'))
    await installed_model.add(mods[0])

    loaded_model = create_model(mockdata)
    await loaded_model.loadInstalled()

    mod = loaded_model[('modDirect', 'mods')]
    assert len(loaded_model) == 2
    assert mod.package == 'direct'
    assert mod.filename == 'modDirect'
    assert mod.datatype == 'mod'
    assert mod.installed is True
    assert mod.enabled is True
    assert content_files(mod) == ['content/blob0.bundle', 'content/metadata.store']
