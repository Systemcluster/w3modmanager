from w3modmanager.util import util

from loguru import logger

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Union
from configparser import ConfigParser
import itertools
import re


#
# string formatting
#

def formatPackageName(name: str) -> str:
    # remove file extension
    if re.search(r'. *\.(zip|rar|tar)$', name, re.IGNORECASE):
        name = name[:-4]
    elif re.search(r'.*\.7z$', name, re.IGNORECASE):
        name = name[:-3]
    elif re.search(r'.*\.lzma$', name, re.IGNORECASE):
        name = name[:-5]
    # remove nexusmods version suffix
    length = len(name)
    for match in re.finditer(r'-[0-9]+-.+', name):
        length = match.span()[0]
    name = name[0:length]
    # remove mod prefix if package name is long enough
    if re.match('^mod.*', name, re.IGNORECASE) and length > 6:
        name = name[3:]
    # remove leading and trailing non-alphanumeric characters
    name = re.sub(r'^[^a-zA-Z0-9]*(.*)[^a-zA-Z0-9]*$', r'\1', name)
    # insert spacing
    name = re.sub(r'([a-z]{2,})(?=[A-Z1-9])', r'\1 ', name)
    name = re.sub(r'([A-Z][a-z])(?=[A-Z]{2}|[1-9])', r'\1 ', name)
    name = re.sub(r'(_)', r' ', name)
    name = re.sub(r'([a-zA-Z])-(?=[0-9])', r'\1 ', name)
    name = re.sub(r'([0-9])-?(?=[a-zA-Z])', r'\1 ', name)
    return name


def formatModName(name: str, prefix: str = '') -> str:
    # remove trailing file copy suffix
    name = re.sub(r'(-[ ]*Copy)+$', '', name)
    name = re.sub(r'([ ]*\([0-9]+\))$', '', name)
    # remove non-alphanumeric characters
    name = re.sub(r'[^a-zA-Z0-9-_ ]', '', name)
    # remove infix versions
    name = re.sub(r'( ([vVxX]?[0-9.]+)* )', r' ', name)
    # join separated words and uppercase following characters
    name = re.sub(r'(?<=[a-zA-Z0-9])(?:[- ]|(?!___)[_])+([a-zA-Z0-9])',
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
        if name[:3].lower() == 'mod' and len(name) > 6:
            name = name[3:]
        name = prefix + name[:1].upper() + name[1:]
    else:
        name = name[:pl].lower() + name[pl:pl + 1].upper() + name[pl + 1:]
    return name


def formatDlcName(name: str):
    # remove trailing file copy suffix
    name = re.sub(r'(-[ ]*Copy)+$', '', name)
    name = re.sub(r'([ ]*\([0-9]+\))$', '', name)
    # remove non-alphanumeric characters
    name = re.sub(r'[^a-zA-Z0-9-_ ]', '', name)
    return name


#
# mod validation
#

def containsValidMod(path: Path, searchlimit=0) -> Tuple[bool, bool]:
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
            dirs += sorted([d for d in check.iterdir() if d.is_dir()])
            if searchlimit and len(dirs) > searchlimit:
                return False, False
    return False, True


def isValidModDirectory(path: Path) -> bool:
    # valid if path starts with mod and contains a non-empty content dir
    # and is not contained in a dlc dir
    if path.is_dir() \
    and re.match('^(mod).*', path.name, re.IGNORECASE) \
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
    return 'content' in [d.name.lower() for d in path.iterdir() if d.is_dir() and d.iterdir()]


def containsScripts(path: Path) -> bool:
    # check if path contains .ws scripts inside content/scripts/
    for f in path.glob("content/**/*.ws"):
        if f.is_file():
            return True
    return False


#
# mod directory extraction
#

def fetchModDirectories(path: Path) -> List[Path]:
    bins = []
    dirs = [path]
    for check in dirs:
        if isValidModDirectory(check):
            bins.append(check.relative_to(path))
        elif not isValidDlcDirectory(check):
            dirs += sorted([d for d in check.iterdir() if d.is_dir()])
    return bins


def fetchDlcDirectories(path: Path) -> List[Path]:
    bins = []
    dirs = [path]
    for check in dirs:
        if isValidDlcDirectory(check):
            bins.append(check.relative_to(path))
        elif not isValidModDirectory(check):
            dirs += sorted([d for d in check.iterdir() if d.is_dir()])
    return bins


def fetchUnsureDirectories(path: Path) -> List[Path]:
    bins = []
    dirs = [path]
    for check in dirs:
        if maybeModOrDlcDirectory(check, path):
            bins.append(check.relative_to(path))
        dirs += sorted([
            d for d in check.iterdir() if d.is_dir()
            and not isValidModDirectory(d) and not isValidDlcDirectory(d)
        ])
    return bins


#
# mod file extraction
#

@dataclass
class BinFile:
    source: Path
    target: Path

    def __repr__(self) -> str:
        if self.source == self.target:
            return '\'%s\'' % str(self.source)
        else:
            return '\'%s (%s)\'' % (str(self.source), str(self.target))

    def __eq__(self, other):
        if isinstance(other, BinFile):
            return self.source == other.source and self.target == other.target
        if isinstance(other, str):
            if self.source == self.target:
                return self.source == Path(other)
            match = re.findall(r'^(.*) \((.*)\)$', other)
            if len(match) != 1 or len(match[0]) != 2:
                return False
            return match and self.source == Path(match[0][0]) \
                and self.target == Path(match[0][1])


@dataclass
class ContentFile:
    source: Path

    def __repr__(self) -> str:
        return '\'%s\'' % str(self.source)

    def __eq__(self, other):
        if isinstance(other, ContentFile):
            return self.source == other.source
        if isinstance(other, str):
            return self.source == Path(other)


@dataclass(init=False)
class Settings:
    source: Path
    config: ConfigParser

    def __init__(self, source: Path, content: str):
        self.source = source
        self.config = ConfigParser(strict=False)
        self.config.optionxform = str  # type: ignore

        # remove any instructions or comments included at the top of the file
        cleanContent = content.splitlines()
        start = 0
        for line in cleanContent:
            if line.strip().startswith('['):
                break
            start += 1
        self.config.read_string('\n'.join(cleanContent[start:]))

    def __repr__(self) -> str:
        return '\'%s\': %s' % (
            str(self.source),
            str({section: dict(self.config[section]) for section in self.config.sections()}))


class UserSettings(Settings):
    pass


class InputSettings(Settings):
    pass


def fetchBinFiles(path: Path, onlyUngrouped: bool = False) -> \
        Tuple[List[BinFile], List[UserSettings], List[InputSettings]]:
    bins = []
    user = []
    inpu = []
    dirs = [path]
    for check in dirs:
        for file in sorted([
            f for f in check.iterdir()
            if f.is_file() and f.suffix.lower() in ('.ini', '.xml', '.txt', '.settings', '.dll', '.asi')
        ]):
            relpath: Path = file.relative_to(path)

            # if the binfile is placed under bin, use its path relative to its bin dir
            if 'bin' in relpath.parts:
                minpath = Path(re.sub(r'^((?!bin\\|bin\/).)*', r'', str(relpath), flags=re.IGNORECASE))
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

            # detect dll and asi files
            if re.match(r'.+(\.dll|\.asi)$', relpath.name, re.IGNORECASE):
                bins.append(BinFile(
                    relpath,
                    Path(f'bin/x64/{relpath.name}')
                ))
                # add cfgs coming with it
                bins.extend(sorted([BinFile(
                    cfg.relative_to(path),
                    Path(f'bin/x64/{cfg.name}')
                ) for cfg in file.parent.iterdir()
                    if re.match(r'.+(\.cfg)$', cfg.name, re.IGNORECASE) and cfg not in bins
                ]))

            # detect input.settings
            if re.match(r'.*input[.]?s(ettings)?(\.part)?(\.txt)?$', relpath.name, re.IGNORECASE):
                try:
                    inpu.append(InputSettings(relpath, util.readText(file)))
                except Exception:
                    logger.bind(file=file).debug('Could not parse input settings')
                continue

            # detect user.settings
            if re.match(r'.*user[.]?(settings)?(\.part)?(\.txt)?$', relpath.name, re.IGNORECASE):
                try:
                    user.append(UserSettings(relpath, util.readText(file)))
                except Exception:
                    logger.bind(file=file).debug('Could not parse user settings')
                continue

        dirs += sorted([
            d for d in check.iterdir()
            if d.is_dir() and (
                not onlyUngrouped
                or not isValidModDirectory(d)
                and not isValidDlcDirectory(d)
                and not maybeModOrDlcDirectory(d, path)
            )
        ])
    return (bins, user, inpu)


def fetchContentFiles(path: Path) -> List[ContentFile]:
    contents = []
    dirs = [path]
    for check in dirs:
        if check.is_dir() and check.name == 'content':
            contents.extend([
                ContentFile(x.relative_to(path))
                for x in check.glob('**/*') if x.is_file()
            ])
        else:
            dirs += sorted([d for d in check.iterdir() if d.is_dir()])
    return contents


def fetchPatchFiles(path: Path) -> List[ContentFile]:
    contents = []
    for check in sorted([d for d in path.iterdir() if d.is_dir() and d.name == 'content']):
        contents.extend([
            ContentFile(x.relative_to(path))
            for x in sorted(check.glob('**/*')) if x.is_file()
        ])
    return contents


def resolveCommonBinRoot(root: Path, files: List[BinFile]) -> Path:
    # find the innermost common root path for bin files
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
        file.source = file.source.relative_to(common)
    return root.joinpath(common)


#
# path detection
#

def findGamePath() -> Union[Path, None]:
    # Try to find the game path through registry entries and library files
    from w3modmanager.core.model import verifyGamePath
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
        game = winreg.QueryValueEx(subkey, 'exe')
        game = Path(str(game[0]))
        if verifyGamePath(game):
            return game
    except Exception:
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
        steam = winreg.QueryValueEx(subkey, 'installPath')
        steam = Path(str(steam[0]))
        libs = steam.joinpath('steamapps/libraryfolders.vdf')
        if steam.exists() and libs.is_file():
            # found Steam installation, now read library folders manifest
            # and iterate libraries
            libdict = vdf.loads(util.readText(libs), mapper=vdf.VDFDict)
            libvals = libdict['LibraryFolders']
            for key in libvals:
                checkpath = Path(libvals[key])
                if checkpath.is_dir() and checkpath.joinpath('steamapps').is_dir():
                    # Steam library path found, now check for Witcher 3 installation
                    steamapps = checkpath.joinpath('steamapps')
                    game = steamapps.joinpath('common/The Witcher 3/bin/x64/witcher3.exe')
                    if verifyGamePath(game):
                        return game
        else:
            pass
    except Exception:
        # probably not found
        pass

    return None


def findConfigPath() -> Union[Path, None]:
    from w3modmanager.core.model import verifyConfigPath

    path = util.getUserDocumentsPath().joinpath('The Witcher 3')
    return verifyConfigPath(path)
