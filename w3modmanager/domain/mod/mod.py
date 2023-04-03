from __future__ import annotations

from w3modmanager.util.util import *
from w3modmanager.domain.mod.fetcher import *

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Type
from pathlib import Path

from loguru import logger
from dataclasses_json import DataClassJsonMixin, config as JsonConfig


@dataclass
class Mod(DataClassJsonMixin):

    package: str = ''
    filename: str = ''
    priority: int = -1
    installed: bool = False
    enabled: bool = True
    datatype: str = 'mod'
    target: str = 'mods'
    installdate: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    source: Path = field(metadata=JsonConfig(encoder=str, decoder=Path), default_factory=Path)
    size: int = 0
    md5hash: str = ''

    version: str = ''
    category: str = ''
    summary: str = ''
    modid: int = -1
    fileid: int = -1
    uploaddate: datetime = field(default_factory=lambda: datetime.fromtimestamp(0, tz=timezone.utc))
    uploadname: str = ''

    files: List[BinFile] = field(default_factory=list)
    contents: List[ContentFile] = field(default_factory=list)
    settings: List[UserSettings] = field(default_factory=list)
    inputs: List[InputSettings] = field(default_factory=list)
    bundled: List[BundledFile] = field(default_factory=list)

    dataversion: int = 1


    def __getitem__(self, attr: str) -> Any:
        return getattr(self, attr)

    def __lt__(self, other: Mod) -> bool:
        if self.datatype not in ('mod', 'udf',) or other.datatype not in ('mod', 'udf',):
            if self.datatype == other.datatype:
                return self.filename < other.filename
            return self.datatype < other.datatype
        if self.enabled != other.enabled:
            return self.enabled > other.enabled
        if self.priority == other.priority:
            return self.filename < other.filename
        if self.priority <= -2 and other.priority > -2:
            return False
        if self.priority <= -1 and other.priority > -1:
            return False
        if other.priority <= -2 and self.priority > -2:
            return True
        if other.priority <= -1 and self.priority > -1:
            return True
        return self.priority < other.priority

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mod):
            return False
        return self.datatype == other.datatype and self.filename == other.filename

    def __hash__(self) -> int:
        return hash((self.datatype, self.filename))


    @property
    def contentFiles(self) -> List[ContentFile]:
        return list(filter(
            lambda f: f.source.suffix != '.ws',
            self.contents))

    @property
    def scriptFiles(self) -> List[ContentFile]:
        return list(filter(
            lambda f: f.source.suffix == '.ws',
            self.contents))

    @property
    def binFiles(self) -> List[BinFile]:
        return list(filter(
            lambda f: f.target.parent not in (
                Path('bin/config/r4game/user_config_matrix/pc'),
            ),
            self.files))

    @property
    def menuFiles(self) -> List[BinFile]:
        return list(filter(
            lambda f: f.target.parent in (
                Path('bin/config/r4game/user_config_matrix/pc'),
            ), self.files))

    @property
    def bundledFiles(self) -> List[BundledFile]:
        return self.bundled


    @classmethod
    async def fromDirectory(
        cls: Type[Mod], path: Path, searchCommonRoot: bool = True, recursive: bool = True
    ) -> List[Mod]:
        if not os.path.isdir(path):
            raise InvalidPathError(path, 'Invalid mod')
        mods: List[Mod] = []
        dirs = [path]
        if len(list(path.iterdir())) == 1 \
                and len([d for d in path.iterdir() if d.is_dir() and d.name[:3].lower() not in ('dlc', 'mod',) \
                         and d.name not in ('content',) and len(d.name) > 3]) == 1:
            # if directory contains only one subdirectory and it's not the mod, dlc or content dir,
            # use it for the package name
            package = formatPackageName(list(path.iterdir())[0].name)
        else:
            package = formatPackageName(path.name)
        for check in dirs:
            if check.is_dir():
                # fetch mod dirs
                if isValidModDirectory(check):
                    name = formatModName(check.name, 'mod')
                    logger.bind(name=name, path=check).debug('Detected MOD')
                    size = 0
                    files, settings, inputs = fetchBinFiles(check)
                    contents = fetchContentFiles(check)
                    bundled = []
                    for _file in files:
                        size += check.joinpath(_file.source).stat().st_size
                    for _content in contents:
                        size += check.joinpath(_content.source).stat().st_size
                        if _content.source.suffix == '.bundle':
                            bundled.extend(await fetchBundleContents(check, check.joinpath(_content.source)))
                    mods.append(cls(
                        package,
                        filename=name,
                        datatype='mod',
                        target='mods',
                        priority=-1,
                        source=check,
                        size=size,
                        files=files,
                        settings=settings,
                        inputs=inputs,
                        contents=contents,
                        bundled=bundled
                    ))
                    continue
                # fetch dlc dirs
                elif isValidDlcDirectory(check):
                    name = formatDlcName(check.name)
                    logger.bind(name=name, path=check).debug('Detected DLC')
                    size = 0
                    files, settings, inputs = fetchBinFiles(check)
                    contents = fetchContentFiles(check)
                    bundled = []
                    for _file in files:
                        size += check.joinpath(_file.source).stat().st_size
                    for _content in contents:
                        size += check.joinpath(_content.source).stat().st_size
                        if _content.source.suffix == '.bundle':
                            bundled.extend(await fetchBundleContents(check, check.joinpath(_content.source)))
                    mods.append(cls(
                        package,
                        filename=name,
                        datatype='dlc',
                        target='dlc',
                        priority=-2,
                        source=check,
                        size=size,
                        files=files,
                        settings=settings,
                        inputs=inputs,
                        contents=contents,
                        bundled=bundled
                    ))
                    continue
                # fetch unspecified mod or doc dirs
                if maybeModOrDlcDirectory(check, path):
                    name = formatModName(check.name, 'mod')
                    logger.bind(name=name, path=check).debug('Detected MOD')
                    size = 0
                    files, settings, inputs = fetchBinFiles(check)
                    contents = fetchContentFiles(check)
                    bundled = []
                    for _file in files:
                        size += check.joinpath(_file.source).stat().st_size
                    for _content in contents:
                        size += check.joinpath(_content.source).stat().st_size
                        if _content.source.suffix == '.bundle':
                            bundled.extend(await fetchBundleContents(check, check.joinpath(_content.source)))
                    mods.append(cls(
                        package,
                        filename=name,
                        datatype='udf',
                        target='mods',
                        priority=-1,
                        source=check,
                        size=size,
                        files=files,
                        settings=settings,
                        inputs=inputs,
                        contents=contents,
                        bundled=bundled
                    ))
                    continue
                if recursive:
                    dirs += sorted(d for d in check.iterdir() if d.is_dir())
        # fetch loose bin files
        files, settings, inputs = fetchBinFiles(path, onlyUngrouped=True)
        if searchCommonRoot:
            commonroot = resolveCommonBinRoot(path, files)
        else:
            commonroot = path
        if files:
            name = formatModName(commonroot.name, 'bin')
            logger.bind(name=name, path=commonroot).debug('Detected BIN')
            size = 0
            for file in files:
                size += commonroot.joinpath(file.source).stat().st_size
            mods.append(cls(
                package,
                filename=name,
                datatype='bin',
                target='mods',
                priority=-2,
                source=commonroot,
                size=size,
                files=files,
                settings=settings,
                inputs=inputs
            ))
        # fetch patch files
        if len(mods) == 1 and mods[0].filename == 'mod0000____CompilationTrigger':
            contents = fetchPatchFiles(path)
            if contents:
                name = formatModName(path.name, 'pat')
                logger.bind(name=name, path=path).debug('Detected PAT')
                size = 0
                bundled = []
                for _content in contents:
                    size += path.joinpath(_content.source).stat().st_size
                    if _content.source.suffix == '.bundle':
                        bundled.extend(await fetchBundleContents(check, path.joinpath(_content.source)))
                mods.append(cls(
                    package,
                    filename=name,
                    datatype='pat',
                    target='mods',
                    priority=-2,
                    source=path,
                    size=size,
                    settings=settings,
                    inputs=inputs,
                    contents=contents,
                    bundled=bundled
                ))
        if not mods:
            raise InvalidPathError(path, 'Invalid mod')
        return mods
