from __future__ import annotations

from w3modmanager.core.errors import (
    InvalidCachePath,
    InvalidConfigPath,
    InvalidDlcsPath,
    InvalidGamePath,
    InvalidModsPath,
    InvalidPathError,
    InvalidSourcePath,
    ModExistsError,
    ModNotFoundError,
    OtherInstanceError,
)
from w3modmanager.domain.bin.modifier import (
    addSettings,
    removeSettings,
)
from w3modmanager.domain.bin.watcher import CallbackList, WatchedConfigFile
from w3modmanager.domain.mod.fetcher import BundledFile, ContentFile
from w3modmanager.domain.mod.mod import Mod
from w3modmanager.util.util import debounce, removeDirectory

import asyncio
import contextlib
import re

from collections.abc import Iterator, KeysView, ValuesView
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from shutil import copyfile

from fasteners import InterProcessLock
from loguru import logger


ModelIndexType = Mod | tuple[str, str] | int
'''The type for indexing the model - options are mod, (modname, target) tuple, or index'''


@dataclass
class ModelConflicts:
    bundled: dict[str, dict[BundledFile, str]] = field(default_factory=dict)
    scripts: dict[str, dict[ContentFile, str]] = field(default_factory=dict)
    iteration: int = 0

    @classmethod
    def fromModList(
        cls: type[ModelConflicts], modList: dict[tuple[str, str], Mod], iteration: int
    ) -> ModelConflicts:
        existingsBundled: dict[BundledFile, str] = {}
        conflictsBundled: dict[str, dict[BundledFile, str]] = {}
        existingsScripts: dict[ContentFile, str] = {}
        conflictsScripts: dict[str, dict[ContentFile, str]] = {}
        for mod in sorted(mod for mod in modList.values() if mod.enabled and mod.datatype in ('mod', 'udf',)):
            conflictsBundled[mod.filename] = {}
            conflictsScripts[mod.filename] = {}
            for bundledFile in mod.bundledFiles:
                if bundledFile in existingsBundled:
                    conflictsBundled[mod.filename][bundledFile] = existingsBundled[bundledFile]
                else:
                    existingsBundled[bundledFile] = mod.filename
            for scriptFile in mod.scriptFiles:
                if scriptFile in existingsScripts:
                    conflictsScripts[mod.filename][scriptFile] = existingsScripts[scriptFile]
                else:
                    existingsScripts[scriptFile] = mod.filename
        return cls(
            bundled=conflictsBundled,
            scripts=conflictsScripts,
            iteration=iteration
        )


class Model:
    """The mod management model"""

    def __init__(self, gamePath: Path, configPath: Path, cachePath: Path, ignorelock: bool = False) -> None:
        self._gamePath: Path = Path()
        self._configPath: Path = Path()
        self._cachePath: Path = Path()
        self._modsPath: Path = Path()
        self._dlcsPath: Path = Path()

        self._modList: dict[tuple[str, str], Mod] = {}
        self._lock = None
        self._pool = None

        _cachePath = verifyCachePath(cachePath)
        if not _cachePath:
            raise InvalidCachePath(cachePath)
        self._cachePath = _cachePath

        self.setPaths(gamePath, configPath)

        self.updateCallbacks = CallbackList()
        self.updateLock = asyncio.Lock()

        self.conflicts = ModelConflicts()
        self._pool = ProcessPoolExecutor()
        self._iteration = 0

        self._lock = InterProcessLock(self.lockfile)
        if not self._lock.acquire(False):
            if ignorelock:
                self._lock = None
            else:
                raise OtherInstanceError(self.lockfile)

        self._modsSettings = WatchedConfigFile(self.configpath.joinpath('mods.settings'))
        self._modsSettings.watcher.callbacks.append(lambda _: self.readModsSettings())

        # TODO: enhancement: watch mod directory for changes

        logger.debug('Initialized model')
        logger.debug(f'Game path: {self._gamePath}')
        logger.debug(f'Config path: {self._configPath}')
        logger.debug(f'Cache path: {self._cachePath}')
        logger.debug(f'Mods path: {self._modsPath}')

        # TODO: incomplete: implement mod installation management


    def setPaths(self, gamePath: Path, configPath: Path) -> None:
        _gamePath = verifyGamePath(gamePath)
        _configPath = verifyConfigPath(configPath)

        if self._gamePath == _gamePath and self._configPath == _configPath:
            return

        if not _gamePath:
            raise InvalidGamePath(gamePath)
        if not _configPath:
            raise InvalidConfigPath(configPath)

        modsPath = _gamePath.joinpath('Mods')
        _modsPath = verifyModsPath(modsPath)
        dlcsPath = _gamePath.joinpath('DLC')
        _dlcsPath = verifyDlcsPath(dlcsPath)

        if not _modsPath:
            raise InvalidModsPath(modsPath)
        if not _dlcsPath:
            raise InvalidDlcsPath(dlcsPath)

        self._gamePath = _gamePath
        self._configPath = _configPath
        self._modsPath = _modsPath
        self._dlcsPath = _dlcsPath

        self.lastUpdate = datetime.now(tz=timezone.utc)
        self.lastInitialization = datetime.now(tz=timezone.utc)

        self._modList = {}


    @debounce(25)
    async def updateBundledContentsConflicts(self) -> None:
        self._iteration += 1
        conflicts = await asyncio.get_running_loop().run_in_executor(
            self._pool,
            partial(ModelConflicts.fromModList, self._modList, self._iteration)
        )
        if conflicts.iteration == self._iteration:
            self.conflicts = conflicts
            self.updateCallbacks.fire(self)


    async def loadInstalledMod(self, path: Path) -> None:
        if path.joinpath('.w3mm').is_file():
            try:
                mod = Mod.from_json(path.joinpath('.w3mm').read_bytes())
                mod.enabled = not path.name.startswith('~')
                mod.filename = re.sub(r'^(~)', r'', path.name)
                if mod.enabled:
                    enabled = self._modsSettings.getValue(mod.filename, 'Enabled', '1')
                    if enabled == '0':
                        mod.enabled = False
                    priority = self._modsSettings.getValue(mod.filename, 'Priority', fallback=mod.priority)
                    with contextlib.suppress(ValueError):
                        mod.priority = int(priority)

                if (mod.filename, mod.target) in self._modList:
                    logger.bind(path=path).error('Ignoring duplicate MOD')
                    if not self._modList[(mod.filename, mod.target)].enabled:
                        self._modList[(mod.filename, mod.target)] = mod
                else:
                    self._modList[(mod.filename, mod.target)] = mod
                # TODO: incomplete: detect changed files
            except Exception as e:
                logger.bind(path=path).exception(f'Could not load MOD: {e}')
        else:
            try:
                for mod in await Mod.fromDirectory(path, recursive=False):
                    mod.installdate = datetime.fromtimestamp(path.stat().st_ctime, tz=timezone.utc)
                    mod.target = 'mods'
                    mod.enabled = not path.name.startswith('~')
                    mod.filename = re.sub(r'^(~)', r'', path.name)
                    priority = self._modsSettings.getValue(mod.filename, 'Priority', mod.priority)
                    with contextlib.suppress(ValueError):
                        mod.priority = int(priority)

                    if mod.enabled:
                        enabled = self._modsSettings.getValue(mod.filename, 'Enabled', '1')
                        if enabled == '0':
                            mod.enabled = False
                    if (mod.filename, mod.target) in self._modList:
                        logger.bind(path=path).error('Ignoring duplicate MOD')
                        if not self._modList[(mod.filename, mod.target)].enabled:
                            self._modList[(mod.filename, mod.target)] = mod
                    else:
                        self._modList[(mod.filename, mod.target)] = mod
                        await self.update(mod)
            except InvalidPathError:
                logger.bind(path=path).debug('Invalid MOD')

    async def loadInstalledDlc(self, path: Path) -> None:
        if path.joinpath('.w3mm').is_file():
            try:
                mod = Mod.from_json(path.joinpath('.w3mm').read_bytes())
                mod.enabled = not all(file.name.endswith('.disabled')
                                      for file in path.glob('**/*') if file.is_file()
                                      and file.name != '.w3mm')
                mod.filename = path.name
                self._modList[(mod.filename, mod.target)] = mod
            except Exception as e:
                logger.bind(path=path).exception(f'Could not load DLC: {e}')
        else:
            try:
                for mod in await Mod.fromDirectory(path, recursive=False):
                    mod.installdate = datetime.fromtimestamp(path.stat().st_ctime, tz=timezone.utc)
                    mod.target = 'dlc'
                    mod.datatype = 'dlc'
                    mod.enabled = not all(file.name.endswith('.disabled')
                                          for file in path.glob('**/*') if file.is_file()
                                          and file.name != '.w3mm')
                    mod.filename = path.name
                    self._modList[(mod.filename, mod.target)] = mod
                    await self.update(mod)
            except InvalidPathError:
                logger.bind(path=path).debug('Invalid DLC')

    async def loadInstalled(self) -> None:
        await asyncio.gather(
            *[self.loadInstalledMod(path) for path in self.modspath.iterdir()]
        )
        await asyncio.gather(
            *[self.loadInstalledDlc(path) for path in self.dlcspath.iterdir()]
        )
        self.updateBundledContentsConflicts()
        self.updateCallbacks.fire(self)


    def get(self, mod: ModelIndexType) -> Mod:
        return self[mod]

    def keys(self) -> KeysView[tuple[str, str]]:
        return self._modList.keys()

    def values(self) -> ValuesView[Mod]:
        return self._modList.values()

    def data(self) -> dict[tuple[str, str], Mod]:
        return self._modList


    async def add(self, mod: Mod) -> None:
        # TODO: incomplete: always override compilation trigger mod
        if self.modspath in [mod.source, *mod.source.parents]:
            raise InvalidSourcePath(mod.source, 'Invalid mod source: Mods cannot be installed from the mods directory')
        async with self.updateLock:
            if (mod.filename, mod.target) in self._modList:
                raise ModExistsError(mod.filename, mod.target)
            target = self.getModPath(mod)
            if target.exists():
                # TODO: incomplete: make sure the mod is tracked by the model
                raise ModExistsError(mod.filename, mod.target)
            settings = 0
            inputs = 0
            try:
                event_loop = asyncio.get_running_loop()
                target.mkdir(parents=True)
                # copy mod files
                copies = list[tuple[Path, Path]]()
                logger.bind(name=mod.filename, path=target).debug('Copying binary files')
                for _file in mod.files:
                    sourceFile = mod.source.joinpath(_file.source)
                    targetFile = target.joinpath(_file.source)
                    targetFile.parent.mkdir(parents=True, exist_ok=True)
                    copies.append((sourceFile, targetFile))
                await asyncio.gather(*[
                    event_loop.run_in_executor(
                        None,
                        partial(copyfile, _copy[0], _copy[1])) for _copy in copies
                ])
                copies = list[tuple[Path, Path]]()
                logger.bind(name=mod.filename, path=target).debug('Copying content files')
                for _content in mod.contents:
                    sourceFile = mod.source.joinpath(_content.source)
                    targetFile = target.joinpath(_content.source)
                    targetFile.parent.mkdir(parents=True, exist_ok=True)
                    copies.append((sourceFile, targetFile))
                await asyncio.gather(*[
                    event_loop.run_in_executor(
                        None,
                        partial(copyfile, _copy[0], _copy[1])) for _copy in copies
                ])
                mod.installed = True
                # update settings
                logger.bind(name=mod.filename, path=target).debug('Updating settings')
                settings = addSettings(mod.settings, self.configpath.joinpath('user.settings'))
                inputs = addSettings(mod.inputs, self.configpath.joinpath('input.settings'))
                self._modsSettings.setValue(mod.filename, 'Enabled', '1')
                await self.update(mod)
            except Exception as e:
                removeDirectory(target)
                if settings:
                    removeSettings(mod.settings, self.configpath.joinpath('user.settings'))
                if inputs:
                    removeSettings(mod.inputs, self.configpath.joinpath('input.settings'))
                self._modsSettings.removeSection(mod.filename)
                raise e
            self._modList[(mod.filename, mod.target)] = mod
        self._modsSettings.write()
        self.updateBundledContentsConflicts()
        self.setLastUpdateTime(datetime.now(tz=timezone.utc))

    async def update(self, mod: Mod) -> None:
        # serialize and store mod structure
        target = self.getModPath(mod, True)
        try:
            with target.joinpath('.w3mm').open('w', encoding='utf-8') as modInfoFile:
                modSerialized = mod.to_json()
                modInfoFile.write(modSerialized)
        except Exception as e:
            logger.exception(f'Could not update mod: {e}')

    async def replace(self, filename: str, target: str, mod: Mod) -> None:
        # TODO: incomplete: handle possible conflict with existing mods
        async with self.updateLock:
            self._modList[(filename, target)] = mod
        self.updateBundledContentsConflicts()
        self.setLastUpdateTime(datetime.now(tz=timezone.utc))

    async def remove(self, mod: ModelIndexType) -> None:
        if await self.disable(mod):
            async with self.updateLock:
                mod = self[mod]
                target = self.getModPath(mod, True)
                removeDirectory(target)
                try:
                    removeSettings(mod.settings, self.configpath.joinpath('user.settings'))
                except Exception as e:
                    logger.bind(name=mod.filename).warning(f'Could not remove settings from user.settings: {e}')
                try:
                    removeSettings(mod.inputs, self.configpath.joinpath('input.settings'))
                except Exception as e:
                    logger.bind(name=mod.filename).warning(f'Could not remove settings from input.settings: {e}')
                self._modsSettings.removeSection(mod.filename)
                del self._modList[(mod.filename, mod.target)]
            self._modsSettings.write()
            self.updateBundledContentsConflicts()
            self.setLastUpdateTime(datetime.now(tz=timezone.utc))

    async def enable(self, mod: ModelIndexType) -> bool:
        async with self.updateLock:
            mod = self[mod]
            oldstat = mod.enabled
            oldpath = self.getModPath(mod, True)
            renamed = False
            undo = False
            renames = list[Path]()
            settings = 0
            inputs = 0
            try:
                mod.enabled = True
                if mod.target == 'mods':
                    newpath = self.getModPath(mod)
                    if oldpath != newpath:
                        oldpath.rename(newpath)
                        renamed = True
                    self._modsSettings.setValue(mod.filename, 'Enabled', '1')
                if mod.target == 'dlc':
                    for file in oldpath.glob('**/*'):
                        while file.is_file() and file.suffix == '.disabled':
                            renamed = file.rename(file.with_suffix(''))
                            renames.append(renamed)
                settings = addSettings(mod.settings, self.configpath.joinpath('user.settings'))
                inputs = addSettings(mod.inputs, self.configpath.joinpath('input.settings'))
                await self.update(mod)
            except PermissionError:
                logger.bind(path=oldpath).exception(
                    'Could not enable mod, invalid permissions. Is it open in the explorer?')
                undo = True
            except Exception as e:
                logger.exception(f'Could not enable mod: {e}')
                mod.enabled = oldstat
                undo = True
            if undo:
                newpath = self.getModPath(mod)
                mod.enabled = oldstat
                if newpath.is_dir() and newpath != oldpath and renamed:
                    newpath.rename(oldpath)
                for rename in reversed(renames):
                    rename.rename(rename.with_suffix(rename.suffix + '.disabled'))
                if settings:
                    removeSettings(mod.settings, self.configpath.joinpath('user.settings'))
                if inputs:
                    removeSettings(mod.inputs, self.configpath.joinpath('input.settings'))
                if mod.datatype in ('mod', 'udf',):
                    self._modsSettings.setValue(mod.filename, 'Enabled', '0')
        # TODO: incomplete: handle xml and ini changes
        if not undo:
            self._modsSettings.write()
            self.updateBundledContentsConflicts()
            self.setLastUpdateTime(datetime.now(tz=timezone.utc))
            return True
        return False

    async def disable(self, mod: ModelIndexType) -> bool:
        async with self.updateLock:
            mod = self[mod]
            oldstat = mod.enabled
            oldpath = self.getModPath(mod, True)
            renamed = False
            undo = False
            renames = list[Path]()
            settings = 0
            inputs = 0
            try:
                mod.enabled = False
                if mod.target == 'mods':
                    newpath = self.getModPath(mod)
                    if oldpath != newpath:
                        oldpath.rename(newpath)
                        renamed = True
                    if mod.datatype in ('mod', 'udf',):
                        self._modsSettings.setValue(mod.filename, 'Enabled', '0')
                if mod.target == 'dlc':
                    for file in oldpath.glob('**/*'):
                        if file.is_file() and file.name != '.w3mm' and file.suffix != '.disabled':
                            renamed = file.rename(file.with_suffix(file.suffix + '.disabled'))
                            renames.append(renamed)
                settings = removeSettings(mod.settings, self.configpath.joinpath('user.settings'))
                inputs = removeSettings(mod.inputs, self.configpath.joinpath('input.settings'))
                await self.update(mod)
            except PermissionError:
                logger.bind(path=oldpath).exception(
                    'Could not disable mod, invalid permissions. Is it open in the explorer?')
                undo = True
            except Exception as e:
                logger.exception(f'Could not disable mod: {e}')
                undo = True
            if undo:
                newpath = self.getModPath(mod)
                mod.enabled = oldstat
                if newpath.is_dir() and newpath != oldpath and renamed:
                    newpath.rename(oldpath)
                for rename in reversed(renames):
                    rename.rename(rename.with_suffix(''))
                if settings:
                    addSettings(mod.settings, self.configpath.joinpath('user.settings'))
                if inputs:
                    addSettings(mod.inputs, self.configpath.joinpath('input.settings'))
                if mod.target == 'mods' and mod.datatype in ('mod', 'udf',):
                    self._modsSettings.setValue(mod.filename, 'Enabled', '1')
        # TODO: incomplete: handle xml and ini changes
        if not undo:
            self._modsSettings.write()
            self.updateBundledContentsConflicts()
            self.setLastUpdateTime(datetime.now(tz=timezone.utc))
            return True
        return False

    async def setFilename(self, mod: ModelIndexType, filename: str) -> None:
        async with self.updateLock:
            mod = self[mod]
            oldname = mod.filename
            oldenabled = mod.enabled
            if filename.startswith('~'):
                filename = re.sub(r'^~', r'', filename)
                mod.enabled = False
                # TODO: incomplete: handle xml and ini changes
            oldpath = self.getModPath(mod, True)
            mod.filename = filename
            newpath = self.getModPath(mod)
            renamed = False
            undo = False
            try:
                if oldpath != newpath:
                    oldpath.rename(newpath)
                    renamed = True
                self._modsSettings.renameSection(oldname, filename)
                await self.update(mod)
            except PermissionError:
                logger.bind(path=oldpath).exception(
                    'Could not rename mod, invalid permissions. Is it open in the explorer?')
                undo = True
            except Exception as e:
                logger.exception(f'Could not rename mod: {e}')
                undo = True
            if undo:
                mod.filename = oldname
                mod.enabled = oldenabled
                if renamed:
                    newpath.rename(oldpath)
                self._modsSettings.renameSection(filename, oldname)
        self.writeModsSettings()
        self.updateBundledContentsConflicts()
        self.setLastUpdateTime(datetime.now(tz=timezone.utc), False)

    async def setPackage(self, mod: ModelIndexType, package: str) -> None:
        async with self.updateLock:
            mod = self[mod]
            mod.package = package
            await self.update(mod)
        self.setLastUpdateTime(datetime.now(tz=timezone.utc), False)

    async def setCategory(self, mod: ModelIndexType, category: str) -> None:
        async with self.updateLock:
            mod = self[mod]
            mod.category = category
            await self.update(mod)
        self.setLastUpdateTime(datetime.now(tz=timezone.utc), False)

    async def setPriority(self, mod: ModelIndexType, priority: int) -> None:
        async with self.updateLock:
            mod = self[mod]
            mod.priority = priority
            if mod.target == 'mods':
                self._modsSettings.setValue(mod.filename, 'Priority', str(priority) if priority >= 0 else '')
            await self.update(mod)
        self._modsSettings.write()
        self.updateBundledContentsConflicts()
        self.setLastUpdateTime(datetime.now(tz=timezone.utc), False)


    def readModsSettings(self) -> None:
        if len(self._modList) == 0:
            return
        for mod in self._modList.values():
            if mod.datatype not in ('mod', 'udf',):
                continue
            enabled = self._modsSettings.getValue(mod.filename, 'Enabled', fallback='1' if mod.enabled else '0')
            priority = self._modsSettings.getValue(mod.filename, 'Priority', fallback=mod.priority)
            mod.enabled = enabled == '1'
            with contextlib.suppress(ValueError):
                mod.priority = int(priority)

        self.updateBundledContentsConflicts()
        self.setLastUpdateTime(datetime.now(tz=timezone.utc))

    def writeModsSettings(self) -> None:
        for mod in self._modList.values():
            if mod.datatype not in ('mod', 'udf',):
                continue
            self._modsSettings.setValue(mod.filename, 'Enabled', '1' if mod.enabled else '0')
            self._modsSettings.setValue(mod.filename, 'Priority', str(mod.priority) if mod.priority >= 0 else '')
        self._modsSettings.write()


    def setLastUpdateTime(self, time: datetime, fireUpdateCallbacks: bool = True) -> None:
        self.lastUpdate = time
        if fireUpdateCallbacks:
            self.updateCallbacks.fire(self)


    def getModPath(self, mod: ModelIndexType, resolve: bool = False) -> Path:
        if not isinstance(mod, Mod):
            mod = self[mod]
        basepath = self.gamepath.joinpath(mod.target).resolve()
        if not mod.enabled and mod.target == 'mods':
            target = basepath.joinpath(f'~{mod.filename}')
        else:
            target = basepath.joinpath(mod.filename)
        if resolve:
            if not mod.enabled and target.is_dir() \
            and target.parent.joinpath(re.sub(r'^~', r'', target.name)).is_dir():
                # if the mod is disabled but there are two directories with each enabled and disabled names,
                # resolve to the non-disabled directory
                target = target.parent.joinpath(re.sub(r'^~', r'', target.name))
            if not target.is_dir():
                if not mod.enabled and target.parent.joinpath(re.sub(r'^~', r'', target.name)).is_dir():
                    target = target.parent.joinpath(re.sub(r'^~', r'', target.name))
                if not target.is_dir():
                    raise ModNotFoundError(mod.filename, mod.target)
        return target


    def __len__(self) -> int:
        return len(self._modList)

    def __getitem__(self, mod: ModelIndexType) -> Mod:
        if isinstance(mod, int):
            return list(self._modList.values())[mod]
        if isinstance(mod, tuple) and len(mod) == 2:
            if mod not in self._modList:
                raise ModNotFoundError(tuple(mod)[0], tuple(mod)[1])
            return self._modList[mod]
        if isinstance(mod, Mod):
            if mod not in self.values():
                raise ModNotFoundError(mod.filename, mod.target)
            return mod
        raise IndexError(f'invalid index type {type(mod)}')


    def __iter__(self) -> Iterator[tuple[str, str]]:
        yield from self._modList

    def __del__(self) -> None:
        if self._lock is not None and self._lock.acquired:
            self._lock.release()
        if self._pool is not None:
            self._pool.shutdown(wait=False)

    @property
    def lockfile(self) -> Path:
        return self._cachePath.joinpath('w3mm.lock')

    @property
    def gamepath(self) -> Path:
        return self._gamePath

    @property
    def configpath(self) -> Path:
        return self._configPath

    @property
    def cachepath(self) -> Path:
        return self._cachePath

    @property
    def modspath(self) -> Path:
        return self._modsPath

    @property
    def dlcspath(self) -> Path:
        return self._dlcsPath


def verifyGamePath(path: Path | None) -> Path | None:
    if not path:
        return None
    try:
        if path.is_file() and path.suffix == '.exe':
            path = path.parents[2]
        return path.resolve() \
            if path.is_dir() \
            and path.joinpath('content').is_dir() \
            and path.joinpath('bin/x64/witcher3.exe').is_file() \
            else None
    except OSError:
        # check for errors here since this method is used with user input
        logger.bind(path=path).debug('Illegal path')
        return None


def verifyConfigPath(path: Path | None) -> Path | None:
    if not path:
        return None
    try:
        return path.resolve() \
            if path \
            and path.is_dir() \
            and path.joinpath('user.settings').is_file() \
            and path.joinpath('input.settings').is_file() \
            else None
    except OSError:
        # check for errors here since this method is used with user input
        logger.bind(path=path).debug('Illegal path')
        return None


def verifyCachePath(path: Path | None) -> Path | None:
    try:
        if not path or path.exists() and not path.is_dir():
            return None
        if not path.exists():
            path.mkdir(parents=True)
        return path.resolve()
    except OSError:
        # check for errors here since this method is used with user input
        logger.bind(path=path).debug('Illegal path')
        return None


def verifyModsPath(path: Path | None) -> Path | None:
    try:
        if not path or path.exists() and not path.is_dir():
            return None
        if not path.exists():
            path.mkdir(parents=True)
        return path.resolve()
    except OSError:
        # check for errors here since this method is used with user input
        logger.bind(path=path).debug('Illegal path')
        return None


def verifyDlcsPath(path: Path | None) -> Path | None:
    try:
        if not path or path.exists() and not path.is_dir():
            return None
        if not path.exists():
            path.mkdir(parents=True)
        return path.resolve()
    except OSError:
        # check for errors here since this method is used with user input
        logger.bind(path=path).debug('Illegal path')
        return None
