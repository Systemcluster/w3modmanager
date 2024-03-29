from w3modmanager.util import util

import itertools
import os
import re

from configparser import ConfigParser
from dataclasses import dataclass, field
from pathlib import Path

from dataclasses_json import DataClassJsonMixin
from dataclasses_json import config as JsonConfig
from loguru import logger


#
# string formatting
#

def formatPackageName(name: str) -> str:
    original = name
    # remove file extension
    extensions = '|'.join(e[1:] for e in util.getSupportedExtensions())
    name = re.sub(rf'.*(\.({extensions}))$', '', name, re.IGNORECASE)
    # remove nexusmods version suffix
    length = len(name)
    for match in re.finditer(r'-[0-9]+-.*', name):
        length = match.span()[0]
    name = name[0:length]
    # remove leading and trailing non-alphanumeric characters
    name = re.sub(r'^[^a-zA-Z0-9]*(.*)[^a-zA-Z0-9]*$', r'\1', name)
    # remove mod prefix if package name is long enough
    if re.match(r'^mod.*', name, re.IGNORECASE) and len(name) > 4:
        name = name[3:]
    # remove leading and trailing non-alphanumeric characters
    name = re.sub(r'^[^a-zA-Z0-9]*(.*)[^a-zA-Z0-9]*$', r'\1', name)
    # replace plus with space
    name = re.sub(r'([a-zA-Z0-9])\++([a-zA-Z0-9])', r'\1 \2', name)
    # insert spacing
    name = re.sub(r'([a-z]{2,})(?=[A-Z1-9])', r'\1 ', name)
    name = re.sub(r'([A-Z][a-z])(?=[A-Z]{2}|[1-9])', r'\1 ', name)
    name = re.sub(r'([_-])', r' ', name)
    name = re.sub(r'([a-zA-Z])-(?=[0-9])', r'\1 ', name)
    name = re.sub(r'([0-9])-?(?=[a-zA-Z]{3,})', r'\1 ', name)
    # replace all whitespace with regular spaces and remove double spacing
    name = re.sub(r'\s+', r' ', name)
    name = name.strip()
    # return orginal name if formatted name is too short
    if len(name) < 2 and len(original) >= 2:
        return original
    return name


def formatModName(name: str, prefix: str = '') -> str:
    original = name
    # remove trailing file copy suffix
    name = re.sub(r'(-[ ]*Copy)+$', '', name)
    name = re.sub(r'([ ]*\([0-9]+\))$', '', name)
    # remove non-alphanumeric characters
    name = re.sub(r'[^a-zA-Z0-9-_ ]', '', name)
    # remove nexusmods version suffix
    length = len(name)
    for match in re.finditer(r'-[0-9]+-.+', name):
        length = match.span()[0]
    name = name[0:length]
    # remove infix versions
    name = re.sub(r'([ -]([vVxX][0-9.]+)*[ -])', r' ', name)
    # join separated words and uppercase following characters
    name = re.sub(r'(?<=[a-zA-Z0-9])(?:[- ]|(?<!00)[_])+([a-zA-Z0-9])',
                  lambda m: m.group(1).upper(), name)
    # remove trailing version
    name = re.sub(r'([vVxX]?[0-9.]+)[ ]*$', r'', name)
    # remove leading and trailing non-alphanumeric characters
    name = re.sub(r'^[^a-zA-Z0-9]*(.*)[^a-zA-Z0-9]*$', r'\1', name)
    # add prefix and capitalize
    pl = len(prefix)
    if prefix and name[:pl].lower() != prefix.lower():
        # always remove existing mod prefix if not mod
        # and name is long enough
        if name[:3].lower() == 'mod' and len(name) > 4:
            name = name[3:]
        name = prefix + name[:1].upper() + name[1:]
    else:
        name = name[:pl].lower() + name[pl: pl + 1].upper() + name[pl + 1:]
    if len(name) < 4 and len(original) >= 4:
        return original
    return name


def formatDlcName(name: str) -> str:
    original = name
    # remove trailing file copy suffix
    name = re.sub(r'(-[ ]*Copy)+$', '', name)
    name = re.sub(r'([ ]*\([0-9]+\))$', '', name)
    # remove non-alphanumeric characters
    name = re.sub(r'[^a-zA-Z0-9-_]', '', name)
    if len(name) < 4 and len(original) >= 4:
        return original
    return name


#
# mod validation
#

def containsValidMod(path: Path, searchlimit: int = 0) -> tuple[bool, bool]:
    # valid if contains a valid mod or dlc dir
    dirs = [path]
    for check in dirs:
        if check.is_dir():
            if isValidModDirectory(check) \
            or isValidDlcDirectory(check) \
            or maybeModOrDlcDirectory(check, path):
                return True, True
            bins = fetchBinFiles(check, onlyUngrouped=True)
            if len(bins[0]) or len(bins[1]) or len(bins[2]):
                return True, True
            dirs += sorted(d for d in check.iterdir() if d.is_dir())
            if searchlimit and len(dirs) > searchlimit:
                return False, False
    return False, True


def isValidModDirectory(path: Path) -> bool:
    # valid if path starts with mod and contains a non-empty content dir
    # and is not contained in a dlc dir
    if path.is_dir() \
    and re.match('^((~)?mod).*', path.name, re.IGNORECASE) \
    and not re.match('^(dlc[s]?)$', path.parent.name, re.IGNORECASE) \
    and containsContentDirectory(path):
        return True
    return False


def isValidDlcDirectory(path: Path) -> bool:
    # valid if path starts with dlc and contains a non-empty content dir
    # or ends with dlc and doesn't start with mod
    # or starts with mod and is contained in a dlc dir
    if path.is_dir() and (
        re.match('^(dlc).*', path.name, re.IGNORECASE)
        or re.match('^((?!mod).)*dlc$', path.name, re.IGNORECASE)
        or re.match('^(mod).*', path.name, re.IGNORECASE)
            and re.match('^(dlc[s]?)$', path.parent.name, re.IGNORECASE)
    ):
        return containsContentDirectory(path)
    return False


def maybeModOrDlcDirectory(path: Path, root: Path) -> bool:
    # desperate check for mods with invalid naming.
    # if only one dir in root and it contains a content dir,
    # it's probably a misnamed mod or dlc
    if path.is_dir() and path.parent.samefile(root) \
    and any(d for d in path.iterdir() if d.is_dir()):
        return containsContentDirectory(path)
    return False


def containsContentDirectory(path: Path) -> bool:
    # check if a non-empty content folder is contained
    return 'content' in (d.name.lower() for d in path.iterdir() if d.is_dir() and d.iterdir())


def containsScripts(path: Path) -> bool:
    # check if path contains .ws scripts inside content/scripts/
    return any(f.is_file() for f in path.glob('content/**/*.ws'))


#
# mod directory extraction
#

def fetchModDirectories(path: Path) -> list[Path]:
    bins = []
    dirs = [path]
    for check in dirs:
        if isValidModDirectory(check):
            bins.append(check.relative_to(path))
        elif not isValidDlcDirectory(check):
            dirs += sorted(d for d in check.iterdir() if d.is_dir())
    return bins


def fetchDlcDirectories(path: Path) -> list[Path]:
    bins = []
    dirs = [path]
    for check in dirs:
        if isValidDlcDirectory(check):
            bins.append(check.relative_to(path))
        elif not isValidModDirectory(check):
            dirs += sorted(d for d in check.iterdir() if d.is_dir())
    return bins


def fetchUnsureDirectories(path: Path) -> list[Path]:
    bins = []
    dirs = [path]
    for check in dirs:
        if maybeModOrDlcDirectory(check, path):
            bins.append(check.relative_to(path))
        dirs += sorted(
            d for d in check.iterdir() if d.is_dir()
            and not isValidModDirectory(d) and not isValidDlcDirectory(d)
        )
    return bins


#
# mod file extraction
#

@dataclass
class BinFile:
    source: Path = field(metadata=JsonConfig(encoder=str, decoder=Path), default_factory=Path)
    target: Path = field(metadata=JsonConfig(encoder=str, decoder=Path), default_factory=Path)

    def __repr__(self) -> str:
        if self.source == self.target:
            return '\'%s\'' % str(self.source)
        else:
            return f'\'{self.source!s} ({self.target!s})\''

    def __str__(self) -> str:
        if self.source == self.target:
            return '%s' % str(self.source)
        else:
            return f'{self.source!s} ({self.target!s})'

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BinFile):
            return self.source == other.source and self.target == other.target
        if isinstance(other, str):
            if self.source == self.target:
                return self.source == Path(other)
            match = re.findall(r'^(.*) \((.*)\)$', other)
            if len(match) != 1 or len(match[0]) != 2:
                return False
            return bool(match) and self.source == Path(match[0][0]) \
                and self.target == Path(match[0][1])
        return False

    def __hash__(self) -> int:
        return hash((self.source, self.target))

    def __lt__(self, other: object) -> bool:
        if isinstance(other, BinFile):
            return self.source < other.source
        return False


@dataclass
class ContentFile(DataClassJsonMixin):
    source: Path = field(metadata=JsonConfig(encoder=str, decoder=Path))
    hash: str = ''  # noqa: A003

    def __repr__(self) -> str:
        return '\'%s\'' % str(self.source)

    def __str__(self) -> str:
        return str(self.source)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ContentFile):
            return self.source == other.source
        if isinstance(other, str):
            return self.source == Path(other)
        return False

    def __hash__(self) -> int:
        return hash(self.source)

    def __lt__(self, other: object) -> bool:
        if isinstance(other, ContentFile):
            return self.source < other.source
        return False


@dataclass
class ReadmeFile(DataClassJsonMixin):
    source: Path = field(metadata=JsonConfig(encoder=str, decoder=Path))
    content: str

    def __repr__(self) -> str:
        return '\'%s\'' % str(self.source)

    def __str__(self) -> str:
        return str(self.source)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ReadmeFile):
            return self.source == other.source
        if isinstance(other, str):
            return self.source == Path(other)
        return False

    def __hash__(self) -> int:
        return hash(self.source)

    def __lt__(self, other: object) -> bool:
        if isinstance(other, ReadmeFile):
            return self.source < other.source
        return False


@dataclass
class BundledFile(DataClassJsonMixin):
    source: Path = field(metadata=JsonConfig(encoder=str, decoder=Path))
    bundled: Path = field(metadata=JsonConfig(encoder=str, decoder=Path))

    def __repr__(self) -> str:
        return f'\'{self.source!s}\' (\'{self.bundled!s}\')'

    def __str__(self) -> str:
        return f'{self.source!s} ({self.bundled!s})'

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BundledFile):
            return self.source == other.source and self.bundled == other.bundled
        if isinstance(other, str):
            return self.source == Path(other)
        return False

    def __hash__(self) -> int:
        return hash((self.source, self.bundled))

    def __lt__(self, other: object) -> bool:
        if isinstance(other, BundledFile):
            if self.source == other.source:
                return self.bundled < other.bundled
            return self.source < other.source
        return False


@dataclass(init=False)
class Settings(DataClassJsonMixin):
    source: Path = field(metadata=JsonConfig(encoder=str, decoder=Path))
    content: str

    def __init__(self, source: Path, content: str) -> None:
        self.source = source

        # remove any instructional content or comments
        cleanContent = []
        for line in content.splitlines():
            stripped = line.strip()
            if re.match(r'^([a-zA-Z0-9_]+[ ]?=|\[[a-zA-Z0-9_/]+\]$)', stripped):
                cleanContent.append(stripped)
            if match := re.match(r'^[=]+.*(\[[a-zA-Z0-9_/]+\])', stripped):
                cleanContent.append(match[1])
        self.content = '\n'.join(cleanContent)

        config = ConfigParser(strict=False)
        config.optionxform = str  # type: ignore
        config.read_string(self.content)
        self.config = config

    def __repr__(self) -> str:
        return '\'{}\': {}'.format(
            str(self.source),
            str({section: dict(self.config[section]) for section in self.config.sections()}))

    def __str__(self) -> str:
        return '{}: {}'.format(
            str(self.source),
            str({section: dict(self.config[section]) for section in self.config.sections()}))

    def __len__(self) -> int:
        val = 0
        for n in self.config.sections():
            val += len(self.config.items(n))
        return val


class UserSettings(Settings):
    pass


class InputSettings(Settings):
    pass


def fetchBinFiles(path: Path, onlyUngrouped: bool = False) -> \
        tuple[list[BinFile], list[UserSettings], list[InputSettings]]:
    bins = []
    user = []
    inpu = []
    dirs = [path]
    for check in dirs:
        for file in sorted(
            f for f in check.iterdir()
            if f.is_file() and f.suffix.lower() in ('.ini', '.xml', '.txt', '.settings', '.dll', '.asi')
        ):
            relpath: Path = file.relative_to(path)

            # if the binfile is placed under bin, use its path relative to its bin dir
            if 'bin' in relpath.parts:
                minpath = Path(re.sub(r'^((?!bin\/).)*', r'', relpath.as_posix(), flags=re.IGNORECASE))
                bins.append(BinFile(relpath, minpath))
                continue

            # otherwise guess path based on name
            if re.match(r'.+(\.xml|xml\.txt)$', relpath.name, re.IGNORECASE):
                # guess for input.xml
                if re.match(r'.*input([.]?part)?((\.xml)|([.]?xml\.txt))$', relpath.name, re.IGNORECASE):
                    bins.append(BinFile(
                        relpath,
                        Path('bin/config/r4game/user_config_matrix/pc/input.xml')))
                    continue
                # guess for hidden.xml
                if re.match(r'.*hidden([.]?part)?((\.xml)|([.]?xml\.txt))$', relpath.name, re.IGNORECASE):
                    bins.append(BinFile(
                        relpath,
                        Path('bin/config/r4game/user_config_matrix/pc/hidden.xml')))
                    continue
                # otherwise assume menu xml
                if re.match(r'.+\.xml', relpath.name, re.IGNORECASE):
                    bins.append(BinFile(
                        relpath,
                        Path('bin/config/r4game/user_config_matrix/pc').joinpath(relpath.name)))
                    continue

            # detect loose ini files
            if re.match(r'.+\.ini', relpath.name, re.IGNORECASE):
                bins.append(BinFile(
                    relpath,
                    Path('bin/config/platform/pc').joinpath(relpath.name)))

            # detect dll and asi files
            if re.match(r'.+(\.dll|\.asi)$', relpath.name, re.IGNORECASE):
                bins.append(BinFile(
                    relpath,
                    Path(f'bin/x64/{relpath.name}')
                ))
                # add cfgs coming with it
                bins.extend(sorted(BinFile(
                    cfg.relative_to(path),
                    Path(f'bin/x64/{cfg.name}')
                ) for cfg in file.parent.iterdir()
                    if re.match(r'.+(\.cfg)$', cfg.name, re.IGNORECASE) and cfg not in bins
                ))

            # detect input.settings
            if re.match(r'.*input[.]?s(ettings)?([-_.].+)?(\.part)?(\.txt)?$', relpath.name, re.IGNORECASE):
                try:
                    inpu.append(InputSettings(relpath, util.readText(file)))
                except Exception:
                    logger.bind(path=file).warning('Could not parse input settings')
                continue

            # detect user.settings
            if re.match(r'.*user[.]?(settings)?([-_.].+)?(\.part)?(\.txt)?$', relpath.name, re.IGNORECASE):
                try:
                    user.append(UserSettings(relpath, util.readText(file)))
                except Exception:
                    logger.bind(path=file).warning('Could not parse user settings')
                continue

        dirs += sorted(
            d for d in check.iterdir()
            if d.is_dir() and (
                not onlyUngrouped
                or not isValidModDirectory(d)
                and not isValidDlcDirectory(d)
                and not maybeModOrDlcDirectory(d, path)
            )
        )
    return (bins, user, inpu)


def fetchReadmeFiles(path: Path, onlyUngrouped: bool = False) -> list[ReadmeFile]:
    contents = []
    dirs = [path]
    for check in dirs:
        for file in sorted(
            f for f in check.iterdir()
            if f.is_file() and f.suffix.lower() in ('.txt', '.md')
        ):
            relpath: Path = file.relative_to(path)
            if re.match(r'^(.*readme.*)\.(txt|md)', file.name, re.IGNORECASE):
                contents.append(ReadmeFile(relpath, util.readText(file)))
            dirs += sorted(
                d for d in check.iterdir()
                if d.is_dir() and not onlyUngrouped
            )
    return contents


def fetchContentFiles(path: Path) -> list[ContentFile]:
    contents = []
    dirs = [path]
    for check in dirs:
        if check.is_dir() and check.name == 'content':
            contents.extend([
                ContentFile(x.relative_to(path), util.getXXHash(x))
                for x in check.glob('**/*') if x.is_file()
            ])
        else:
            dirs += sorted(d for d in check.iterdir() if d.is_dir())
    return contents


def fetchPatchFiles(path: Path) -> list[ContentFile]:
    contents = []
    for check in sorted(d for d in path.iterdir() if d.is_dir() and d.name == 'content'):
        contents.extend([
            ContentFile(x.relative_to(path), util.getXXHash(x))
            for x in sorted(check.glob('**/*')) if x.is_file()
        ])
    return contents


def resolveCommonBinRoot(root: Path, files: list[BinFile]) -> Path:
    # find the innermost common root path for bin files
    if not files:
        return root
    common = None
    for file in files:
        parents = file.source.parent.parts
        fileroot = Path(*itertools.takewhile(lambda d: d != 'bin', parents))
        if not common or fileroot in common.parents:
            common = fileroot
            continue
    if not common:
        common = Path('.')
    for file in files:
        while common != '.' and common not in file.source.parents:
            common = common.parent
    for file in files:
        file.source = file.source.relative_to(common)
    return root.joinpath(common)


async def fetchBundleContents(root: Path, path: Path) -> list[BundledFile]:
    logger.bind(path=path).debug('Scanning bundle')
    try:
        return [
            BundledFile(path.relative_to(root), Path(bundled))
            for bundled
            in await util.scanBundle(path)]
    except Exception:
        logger.bind(path=path).warning('Could not parse bundle')
    return []


#
# path detection
#

def findGamePath() -> Path | None:
    # Try to find the game path through registry entries and library files
    from w3modmanager.core.model import verifyGamePath  # noqa: I001
    import winreg
    import vdf

    try:
        # try to read Witcher 3 GOG installation path directly
        # see https://www.gog.com/forum/general/querying_gog_install_path
        key = winreg.OpenKeyEx(
            winreg.HKEY_LOCAL_MACHINE,
            r'SOFTWARE',
            access=(winreg.KEY_READ | winreg.KEY_WOW64_64KEY))
        subkey = winreg.OpenKeyEx(key, r'WOW6432Node\GOG.com\Games\1207664663')
        game = Path(str(winreg.QueryValueEx(subkey, 'exe')[0]))
        if verifyGamePath(game):
            return game
    except Exception:  # noqa
        # probably not found
        pass

    try:
        # try to read Steam installation path
        # see https://stackoverflow.com/questions/34090258/find-steam-games-folder
        key = winreg.OpenKeyEx(
            winreg.HKEY_LOCAL_MACHINE,
            r'SOFTWARE',
            access=(winreg.KEY_READ | winreg.KEY_WOW64_64KEY))
        subkey = winreg.OpenKeyEx(key, r'WOW6432Node\Valve\Steam')
        steam = Path(str(winreg.QueryValueEx(subkey, 'installPath')[0]))
        libs = steam.joinpath('steamapps/libraryfolders.vdf')
        if os.path.isdir(steam) and os.path.isfile(libs):
            # found Steam installation, now read library folders manifest
            # and iterate libraries
            libdict = vdf.loads(util.readText(libs), mapper=vdf.VDFDict)
            libvals = libdict['LibraryFolders']
            for key in libvals:
                checkpath = Path(libvals[key])
                if os.path.isdir(checkpath) and os.path.isdir(checkpath.joinpath('steamapps')):
                    # Steam library path found, now check for Witcher 3 installation
                    steamapps = checkpath.joinpath('steamapps')
                    game = steamapps.joinpath('common/The Witcher 3/bin/x64/witcher3.exe')
                    if verifyGamePath(game):
                        return game
        else:
            pass
    except Exception:  # noqa
        # probably not found
        pass

    return None


def findConfigPath() -> Path | None:
    from w3modmanager.core.model import verifyConfigPath

    path = util.getUserDocumentsPath().joinpath('The Witcher 3')
    return verifyConfigPath(path)
