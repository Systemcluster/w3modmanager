from __future__ import annotations

from w3modmanager.util.util import *
import w3modmanager.domain.mod.fetcher as fetcher

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Type
from pathlib import Path
import tempfile
import shutil

from loguru import logger


@dataclass
class Mod:

    modname: str = ''
    filename: str = ''
    priority: int = -1
    installed: bool = False
    enabled: bool = True
    datatype: str = 'mod'
    date: str = ''
    source: Path = Path()
    package: Path = Path()
    size: int = 0
    version: str = ''
    category: str = ''
    md5hash: str = ''

    files: List[fetcher.BinFile] = field(default_factory=list)
    contents: List[fetcher.ContentFile] = field(default_factory=list)
    settings: List[fetcher.UserSettings] = field(default_factory=list)
    inputs: List[fetcher.InputSettings] = field(default_factory=list)


    def __post_init__(self):
        self.modname = fetcher.formatModName(self.modname)

    def __getitem__(self, attr: str):
        return getattr(self, attr)


    @property
    def contentFiles(self):
        return list(filter(
            lambda f: f.source.suffix != '.ws',
            self.contents))

    @property
    def scriptFiles(self):
        return list(filter(
            lambda f: f.source.suffix == '.ws',
            self.contents))

    @property
    def binFiles(self):
        return list(filter(
            lambda f: f.target.parent not in (
                Path('bin/config/r4game/user_config_matrix/pc'),
            ),
            self.files))

    @property
    def menuFiles(self):
        return list(filter(
            lambda f: f.target.parent in (
                Path('bin/config/r4game/user_config_matrix/pc'),
            ), self.files))


    @classmethod
    def fromPath(cls: Type[Mod], path: Path) -> List[Mod]:
        if path.is_file():
            return cls.fromArchive(path)
        else:
            return cls.fromDirectory(path)

    @classmethod
    def fromArchive(cls: Type[Mod], path: Path, package: Path = None) -> List[Mod]:
        mods: List[Mod] = []
        temp = Path(tempfile.gettempdir()).joinpath('w3modmanager/extract')
        try:
            if isArchive(path):
                logger.bind(path=str(path), dots=True).debug('Unpacking archive')
                target = temp.joinpath(path.name)
                extractArchive(path, target)
                if fetcher.containsValidMod(target):
                    mods = cls.fromDirectory(target)
                else:
                    raise InvalidPathError(path, 'Invalid mod')
            else:
                raise InvalidPathError(path, 'Invalid archive')
        finally:
            if temp.exists():
                shutil.rmtree(temp)
        md5hash = getMD5Hash(path)
        for mod in mods:
            mod.md5hash = md5hash
            mod.source = path
        return mods

    @classmethod
    def fromDirectory(cls: Type[Mod], path: Path, package: Path = None) -> List[Mod]:
        if not package:
            package = path
        mods: List[Mod] = []
        dirs = [path]
        for check in dirs:
            if check.is_dir():
                # fetch mod dirs
                if fetcher.isValidModDirectory(check):
                    logger.bind(name=fetcher.formatFileName(check.name, 'mod')).info("Installing MOD")
                    size = 0
                    for p in check.glob('**/*'):
                        size += p.stat().st_size
                    files, settings, inputs = fetcher.fetchBinFiles(check)
                    mods.append(cls(
                        modname=path.stem,
                        filename=fetcher.formatFileName(check.name, 'mod'),
                        datatype='mod',
                        source=check,
                        package=package,
                        size=size,
                        files=files,
                        settings=settings,
                        inputs=inputs,
                        contents=fetcher.fetchContentFiles(check),
                        date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    ))
                    continue
                # fetch dlc dirs
                elif fetcher.isValidDlcDirectory(check):
                    logger.bind(name=fetcher.formatFileName(check.name, 'dlc')).info("Installing DLC")
                    size = 0
                    for p in check.glob('**/*'):
                        size += p.stat().st_size
                    files, settings, inputs = fetcher.fetchBinFiles(check)
                    mods.append(cls(
                        modname=path.stem,
                        filename=fetcher.formatFileName(check.name, 'dlc'),
                        datatype='dlc',
                        source=check,
                        package=package,
                        size=size,
                        files=files,
                        settings=settings,
                        inputs=inputs,
                        contents=fetcher.fetchContentFiles(check),
                        date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    ))
                    continue
                # fetch unspecified mod or doc dirs
                if fetcher.maybeModOrDlcDirectory(check, path):
                    logger.bind(name=fetcher.formatFileName(check.name, 'mod')).info("Installing MOD")
                    size = 0
                    for p in check.glob('**/*'):
                        size += p.stat().st_size
                    files, settings, inputs = fetcher.fetchBinFiles(check)
                    mods.append(cls(
                        modname=path.stem,
                        filename=fetcher.formatFileName(check.name, 'mod') + 'Udf',
                        datatype='',
                        source=check,
                        package=package,
                        size=size,
                        files=files,
                        settings=settings,
                        inputs=inputs,
                        contents=fetcher.fetchContentFiles(check),
                        date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    ))
                    continue
                dirs += [d for d in check.iterdir() if d.is_dir()]
        # fetch loose bin files
        files, settings, inputs = fetcher.fetchBinFiles(path, onlyUngrouped=True)
        if files:
            logger.bind(name=fetcher.formatFileName(path.stem, 'mod') + 'Bin').info("Installing BIN")
            size = 0
            for file in files:
                size += path.joinpath(file.source).stat().st_size
            mods.append(cls(
                modname=path.stem,
                filename=fetcher.formatFileName(path.stem, 'mod') + 'Bin',
                datatype='bin',
                source=path,
                package=package,
                size=size,
                files=files,
                settings=settings,
                inputs=inputs,
                date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
        if not mods:
            raise InvalidPathError(path, 'Invalid mod')
        return mods
