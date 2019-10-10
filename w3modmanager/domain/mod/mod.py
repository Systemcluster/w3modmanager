from __future__ import annotations

from w3modmanager.util.util import *
import w3modmanager.domain.mod.fetcher as fetcher

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Type
from pathlib import Path

from loguru import logger


@dataclass
class Mod:

    package: str = ''
    filename: str = ''
    priority: int = -1
    installed: bool = False
    enabled: bool = True
    datatype: str = 'mod'
    date: str = ''
    source: Path = Path()
    size: int = 0
    version: str = ''
    category: str = ''
    md5hash: str = ''

    files: List[fetcher.BinFile] = field(default_factory=list)
    contents: List[fetcher.ContentFile] = field(default_factory=list)
    settings: List[fetcher.UserSettings] = field(default_factory=list)
    inputs: List[fetcher.InputSettings] = field(default_factory=list)


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
    def fromDirectory(cls: Type[Mod], path: Path) -> List[Mod]:
        mods: List[Mod] = []
        dirs = [path]
        package = fetcher.formatPackageName(path.name)
        for check in dirs:
            if check.is_dir():
                # fetch mod dirs
                if fetcher.isValidModDirectory(check):
                    name = fetcher.formatFileName(check.name, 'mod')
                    logger.bind(name=name).info("Installing MOD")
                    size = 0
                    for p in check.glob('**/*'):
                        size += p.stat().st_size
                    files, settings, inputs = fetcher.fetchBinFiles(check)
                    mods.append(cls(
                        package,
                        filename=name,
                        datatype='mod',
                        source=check,
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
                    name = fetcher.formatFileName(check.name, 'dlc')
                    logger.bind(name=name).info("Installing DLC")
                    size = 0
                    for p in check.glob('**/*'):
                        size += p.stat().st_size
                    files, settings, inputs = fetcher.fetchBinFiles(check)
                    mods.append(cls(
                        package,
                        filename=name,
                        datatype='dlc',
                        source=check,
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
                    name = fetcher.formatFileName(check.name, 'mod') + 'Udf'
                    logger.bind(name=name).info("Installing MOD")
                    size = 0
                    for p in check.glob('**/*'):
                        size += p.stat().st_size
                    files, settings, inputs = fetcher.fetchBinFiles(check)
                    mods.append(cls(
                        package,
                        filename=name,
                        datatype='',
                        source=check,
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
            name = fetcher.formatFileName(path.name, 'bin')
            logger.bind(name=name).info("Installing BIN")
            size = 0
            for file in files:
                size += path.joinpath(file.source).stat().st_size
            mods.append(cls(
                package,
                filename=name,
                datatype='bin',
                source=path,
                size=size,
                files=files,
                settings=settings,
                inputs=inputs,
                date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
        # fetch patch files
        if len(mods) == 1 and mods[0].filename == 'mod0000____CompilationTrigger':
            contents = fetcher.fetchPatchFiles(path)  # ignore: type
            if contents:
                name = fetcher.formatFileName(path.name, 'pat')
                logger.bind(name=name).info("Installing PAT")
                size = 0
                for content in contents:
                    size += path.joinpath(content.source).stat().st_size
                mods.append(cls(
                    package,
                    filename=name,
                    datatype='pat',
                    source=path,
                    size=size,
                    settings=settings,
                    inputs=inputs,
                    contents=contents,
                    date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
        if not mods:
            raise InvalidPathError(path, 'Invalid mod')
        return mods
