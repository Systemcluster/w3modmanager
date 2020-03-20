from w3modmanager.domain.mod.mod import Mod

from loguru import logger

from pathlib import Path
from typing import Dict, Optional, Union, Tuple, ValuesView, KeysView
from fasteners import InterProcessLock
from datetime import datetime
from asyncio import Lock


class CallbackList(list):
    def fire(self, *args, **kwargs):
        for listener in self:
            listener(*args, **kwargs)


ModelIndexType = Union[Mod, Tuple[str, str], int]
'''The type for indexing the model - options are mod, (modname, target) tuple, or index'''


class Model:
    '''The mod management model'''

    def __init__(self, gamePath: Path, configPath: Path, cachePath: Path, ignorelock: bool = False):
        self._gamePath = verifyGamePath(gamePath)
        self._configPath = verifyConfigPath(configPath)
        self._cachePath = verifyCachePath(cachePath)

        if not verifyGamePath(gamePath):
            raise InvalidGamePath(gamePath)
        if not verifyConfigPath(configPath):
            raise InvalidConfigPath(configPath)
        if not verifyCachePath(cachePath):
            raise InvalidCachePath(cachePath)

        if not ignorelock:
            self._lock = InterProcessLock(self.lockfile)
            if not self._lock.acquire(False):
                raise OtherInstanceError(self.lockfile)

        self.updateCallbacks = CallbackList()
        self.lastUpdate = datetime.utcnow()
        self.updateLock = Lock()

        # TODO: enhancement: watch mod directory for changes

        logger.debug('Initialized model')
        logger.debug(f'Game path: {self._gamePath}')
        logger.debug(f'Config path: {self._configPath}')
        logger.debug(f'Cache path: {self._cachePath}')

        self._modList: Dict[Tuple[str, str], Mod] = {}

        self.loadInstalled()

        # TODO: incomplete: implement mod installation management


    def loadInstalled(self):
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


    def add(self, mod: Mod):
        if (mod.filename, mod.target) in self._modList:
            raise ModExistsError(mod)
        self._modList[(mod.filename, mod.target)] = mod
        self.lastUpdate = datetime.utcnow()
        self.updateCallbacks.fire(self)

    def set(self, filename: str, target: str, mod: Mod):
        self._modList[(filename, target)] = mod
        self.lastUpdate = datetime.utcnow()
        self.updateCallbacks.fire(self)

    def remove(self, mod: ModelIndexType):
        mod = self[mod]
        del self._modList[(mod.filename, mod.target)]
        self.lastUpdate = datetime.utcnow()
        self.updateCallbacks.fire(self)

    def enable(self, mod: ModelIndexType):
        mod = self[mod]
        mod.enabled = True
        self.lastUpdate = datetime.utcnow()
        self.updateCallbacks.fire(self)

    def disable(self, mod: ModelIndexType):
        mod = self[mod]
        mod.enabled = False
        self.lastUpdate = datetime.utcnow()
        self.updateCallbacks.fire(self)


    def setFilename(self, mod: ModelIndexType, filename: str):
        mod = self[mod]
        mod.filename = filename
        self.updateCallbacks.fire(self)

    def setPackage(self, mod: ModelIndexType, package: str):
        mod = self[mod]
        mod.package = package
        self.updateCallbacks.fire(self)

    def setCategory(self, mod: ModelIndexType, category: str):
        mod = self[mod]
        mod.category = category
        self.updateCallbacks.fire(self)

    def setPriority(self, mod: ModelIndexType, priority: int):
        mod = self[mod]
        mod.priority = priority
        self.updateCallbacks.fire(self)


    def setLastUpdateTime(self, time: datetime):
        self.lastUpdate = time
        self.updateCallbacks.fire(self)


    def __len__(self) -> int:
        return len(self._modList)

    def __getitem__(self, mod: ModelIndexType) -> Mod:
        if isinstance(mod, int):
            return list(self._modList.values())[mod]
        if isinstance(mod, tuple) and len(mod) == 2:
            return self._modList[(mod[0], mod[1])]
        if isinstance(mod, Mod) and mod in self.values():
            return mod
        raise IndexError(f'invalid index type {type(mod)}')


    def __iter__(self):
        yield from self._modList

    @property
    def lockfile(self):
        return self._cachePath.joinpath('w3mm.lock')

    @property
    def gamepath(self):
        return self._gamePath

    @property
    def configpath(self):
        return self._configPath

    @property
    def cachepath(self):
        return self._cachePath


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



class ModelError(IOError):
    def __init__(self, path: Path, message: str):
        super().__init__(f'{message}: \'{str(path.resolve())}\'')
        self.path = path


class OtherInstanceError(ModelError):
    def __init__(self, path: Path):
        super().__init__(path, 'Could not lock')


class InvalidGamePath(ModelError):
    def __init__(self, path: Path):
        super().__init__(path, 'Invalid game path')


class InvalidConfigPath(ModelError):
    def __init__(self, path: Path):
        super().__init__(path, 'Invalid config path')


class InvalidCachePath(ModelError):
    def __init__(self, path: Path):
        super().__init__(path, 'Invalid cache path')



class ModError(ValueError):
    pass


class ModExistsError(ModError):
    def __init__(self, mod: Mod):
        super().__init__('Mod already exists: %s' % mod.filename)


class ModNotFoundError(ModError):
    def __init__(self, filename: str):
        super().__init__('Mod not found: %s' % filename)
