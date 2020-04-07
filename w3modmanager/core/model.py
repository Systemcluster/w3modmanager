from w3modmanager.domain.mod.mod import Mod
from w3modmanager.util.util import debounce
from w3modmanager.core.errors import InvalidGamePath, InvalidConfigPath, InvalidCachePath, \
    InvalidModsPath, InvalidSourcePath, OtherInstanceError, ModExistsError, ModNotFoundError

from loguru import logger

from pathlib import Path
from typing import Dict, Optional, Union, Tuple, ValuesView, KeysView, Any, Iterator
from fasteners import InterProcessLock
from datetime import datetime, timezone
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
        _gamePath = verifyGamePath(gamePath)
        _configPath = verifyConfigPath(configPath)
        _cachePath = verifyCachePath(cachePath)

        if not _gamePath:
            raise InvalidGamePath(gamePath)
        if not _configPath:
            raise InvalidConfigPath(configPath)
        if not _cachePath:
            raise InvalidCachePath(cachePath)

        modsPath = _gamePath.joinpath('Mods')
        _modsPath = verifyModsPath(modsPath)

        if not _modsPath:
            raise InvalidModsPath(modsPath)

        self._gamePath: Path = _gamePath
        self._configPath: Path = _configPath
        self._cachePath: Path = _cachePath
        self._modsPath: Path = _modsPath

        if not ignorelock:
            self._lock = InterProcessLock(self.lockfile)
            if not self._lock.acquire(False):
                raise OtherInstanceError(self.lockfile)

        self.updateCallbacks = CallbackList()
        self.lastUpdate = datetime.now(tz=timezone.utc)
        self.updateLock = asyncio.Lock()

        # TODO: enhancement: watch mod directory for changes

        logger.debug('Initialized model')
        logger.debug(f'Game path: {self._gamePath}')
        logger.debug(f'Config path: {self._configPath}')
        logger.debug(f'Cache path: {self._cachePath}')
        logger.debug(f'Mods path: {self._modsPath}')

        self._modList: Dict[Tuple[str, str], Mod] = {}

        self.loadInstalled()

        # TODO: incomplete: implement mod installation management


    def loadInstalled(self) -> None:
        # TODO: incomplete: load installed mods
        pass


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
            self._modList[(mod.filename, mod.target)] = mod
        self.setLastUpdateTime(datetime.now(tz=timezone.utc))

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
        self.setLastUpdateTime(datetime.now(tz=timezone.utc))

    async def disable(self, mod: ModelIndexType) -> None:
        async with self.updateLock:
            mod = self[mod]
            mod.enabled = False
        self.setLastUpdateTime(datetime.now(tz=timezone.utc))

    async def setFilename(self, mod: ModelIndexType, filename: str) -> None:
        async with self.updateLock:
            mod = self[mod]
            mod.filename = filename
        self.setLastUpdateTime(datetime.now(tz=timezone.utc), False)

    async def setPackage(self, mod: ModelIndexType, package: str) -> None:
        async with self.updateLock:
            mod = self[mod]
            mod.package = package
        self.setLastUpdateTime(datetime.now(tz=timezone.utc), False)

    async def setCategory(self, mod: ModelIndexType, category: str) -> None:
        async with self.updateLock:
            mod = self[mod]
            mod.category = category
        self.setLastUpdateTime(datetime.now(tz=timezone.utc), False)

    async def setPriority(self, mod: ModelIndexType, priority: int) -> None:
        async with self.updateLock:
            mod = self[mod]
            mod.priority = priority
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
                raise ModNotFoundError(mod[0], mod[1])
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
