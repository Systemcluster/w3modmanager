from w3modmanager.domain.mod.mod import Mod
from w3modmanager.util.util import debounce, removeDirectory
from w3modmanager.core.errors import InvalidCachePath, InvalidConfigPath, InvalidGamePath, \
    InvalidModsPath, InvalidDlcsPath, InvalidSourcePath, ModExistsError, ModNotFoundError, \
    OtherInstanceError, InvalidPathError

from loguru import logger

from pathlib import Path
from typing import Dict, Optional, Union, Tuple, ValuesView, KeysView, Any, Iterator
from fasteners import InterProcessLock
from datetime import datetime, timezone
from shutil import copyfile
import asyncio


class CallbackList(list):
    def __init__(self) -> None:
        self.fireLock = asyncio.Lock()
        super().__init__()

    @debounce(25)
    async def fire(self, *args: Any, **kwargs: Any) -> None:
        async with self.fireLock:
            for listener in self:
                listener(*args, **kwargs)


ModelIndexType = Union[Mod, Tuple[str, str], int]
'''The type for indexing the model - options are mod, (modname, target) tuple, or index'''


class Model:
    """The mod management model"""

    def __init__(self, gamePath: Path, configPath: Path, cachePath: Path, ignorelock: bool = False) -> None:
        self._gamePath: Path = Path()
        self._configPath: Path = Path()
        self._cachePath: Path = Path()
        self._modsPath: Path = Path()
        self._dlcsPath: Path = Path()

        self._modList: Dict[Tuple[str, str], Mod] = {}

        _cachePath = verifyCachePath(cachePath)
        if not _cachePath:
            raise InvalidCachePath(cachePath)
        self._cachePath = _cachePath

        self.updateCallbacks = CallbackList()
        self.updateLock = asyncio.Lock()

        if not ignorelock:
            self._lock = InterProcessLock(self.lockfile)
            if not self._lock.acquire(False):
                raise OtherInstanceError(self.lockfile)

        self.setPaths(gamePath, configPath)

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
        self.loadInstalled()

        self.updateCallbacks.fire(self)


    def loadInstalled(self) -> None:
        for path in self.modspath.iterdir():
            if path.joinpath('.w3mm').is_file():
                mod = Mod.from_json(path.joinpath('.w3mm').read_bytes())
                self._modList[(mod.filename, mod.target)] = mod
            else:
                try:
                    for mod in Mod.fromDirectory(path, recursive=False):
                        mod.installdate = datetime.fromtimestamp(path.stat().st_ctime, tz=timezone.utc)
                        mod.target = 'mods'
                        mod.datatype = 'mod'
                        mod.enabled = not path.name.startswith('~')
                        self._modList[(mod.filename, mod.target)] = mod
                        asyncio.create_task(self.update(mod))
                except InvalidPathError:
                    logger.bind(path=path).debug('Invalid MOD')
        for path in self.dlcspath.iterdir():
            if path.joinpath('.w3mm').is_file():
                mod = Mod.from_json(path.joinpath('.w3mm').read_bytes())
                self._modList[(mod.filename, mod.target)] = mod
            else:
                try:
                    for mod in Mod.fromDirectory(path, recursive=False):
                        mod.installdate = datetime.fromtimestamp(path.stat().st_ctime, tz=timezone.utc)
                        mod.target = 'dlc'
                        mod.datatype = 'dlc'
                        mod.enabled = not path.name.startswith('~')
                        self._modList[(mod.filename, mod.target)] = mod
                        asyncio.create_task(self.update(mod))
                except InvalidPathError:
                    logger.bind(path=path).debug('Invalid DLC')


    def get(self, mod: ModelIndexType) -> Mod:
        return self[mod]

    def keys(self) -> KeysView[Tuple[str, str]]:
        return self._modList.keys()

    def values(self) -> ValuesView[Mod]:
        return self._modList.values()

    def data(self) -> Dict[Tuple[str, str], Mod]:
        return self._modList


    async def add(self, mod: Mod) -> None:
        # TODO: incomplete: always override compilation trigger mod
        if self.modspath in [mod.source, *mod.source.parents]:
            raise InvalidSourcePath(mod.source, 'Invalid mod source: Mods cannot be installed from the mods directory')
        async with self.updateLock:
            if (mod.filename, mod.target) in self._modList:
                raise ModExistsError(mod.filename, mod.target)
            target: Path = self.gamepath.joinpath(mod.target).joinpath(mod.filename)
            if target.exists():
                # TODO: incomplete: make sure the mod is tracked by the model
                raise ModExistsError(mod.filename, mod.target)
            try:
                target.mkdir(parents=True)
                # copy mod files
                for _file in mod.files:
                    sourceFile = mod.source.joinpath(_file.source)
                    targetFile = target.joinpath(_file.source)
                    targetFile.parent.mkdir(parents=True, exist_ok=True)
                    copyfile(sourceFile, targetFile)
                for _content in mod.contents:
                    sourceFile = mod.source.joinpath(_content.source)
                    targetFile = target.joinpath(_content.source)
                    targetFile.parent.mkdir(parents=True, exist_ok=True)
                    copyfile(sourceFile, targetFile)
                await self.update(mod)
            except Exception as e:
                removeDirectory(target)
                raise e
            self._modList[(mod.filename, mod.target)] = mod
            mod.installed = True
        self.setLastUpdateTime(datetime.now(tz=timezone.utc))

    async def update(self, mod: Mod) -> None:
        target: Path = self.gamepath.joinpath(mod.target).joinpath(mod.filename)
        # serialize and store mod structure
        try:
            with target.joinpath('.w3mm').open('w', encoding='utf-8') as modInfoFile:
                modSerialized = mod.to_json()
                modInfoFile.write(modSerialized)
        except Exception as e:
            raise e

    async def replace(self, filename: str, target: str, mod: Mod) -> None:
        # TODO: incomplete: handle possible conflict with existing mods
        async with self.updateLock:
            self._modList[(filename, target)] = mod
        self.setLastUpdateTime(datetime.now(tz=timezone.utc))

    async def remove(self, mod: ModelIndexType) -> None:
        async with self.updateLock:
            mod = self[mod]
            target = self.gamepath.joinpath(mod.target).joinpath(mod.filename)
            removeDirectory(target)
            del self._modList[(mod.filename, mod.target)]
        self.setLastUpdateTime(datetime.now(tz=timezone.utc))

    async def enable(self, mod: ModelIndexType) -> None:
        async with self.updateLock:
            mod = self[mod]
            mod.enabled = True
            await self.update(mod)
        self.setLastUpdateTime(datetime.now(tz=timezone.utc))

    async def disable(self, mod: ModelIndexType) -> None:
        async with self.updateLock:
            mod = self[mod]
            mod.enabled = False
            await self.update(mod)
        self.setLastUpdateTime(datetime.now(tz=timezone.utc))

    async def setFilename(self, mod: ModelIndexType, filename: str) -> None:
        async with self.updateLock:
            mod = self[mod]
            mod.filename = filename
            await self.update(mod)
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
            await self.update(mod)
        self.setLastUpdateTime(datetime.now(tz=timezone.utc), False)


    def setLastUpdateTime(self, time: datetime, fireUpdateCallbacks: bool = True) -> None:
        self.lastUpdate = time
        if fireUpdateCallbacks:
            self.updateCallbacks.fire(self)


    def __len__(self) -> int:
        return len(self._modList)

    def __getitem__(self, mod: ModelIndexType) -> Mod:
        if isinstance(mod, int):
            return list(self._modList.values())[mod]
        if isinstance(mod, tuple) and len(mod) == 2:
            if mod not in self._modList:
                raise ModNotFoundError(tuple(mod)[0], tuple(mod)[1])
            return self._modList[mod]
        if isinstance(mod, Mod) and mod in self.values():
            return mod
        raise IndexError(f'invalid index type {type(mod)}')


    def __iter__(self) -> Iterator[Tuple[str, str]]:
        yield from self._modList

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


def verifyGamePath(path: Optional[Path]) -> Optional[Path]:
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


def verifyConfigPath(path: Optional[Path]) -> Optional[Path]:
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


def verifyCachePath(path: Optional[Path]) -> Optional[Path]:
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


def verifyModsPath(path: Optional[Path]) -> Optional[Path]:
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


def verifyDlcsPath(path: Optional[Path]) -> Optional[Path]:
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
