from w3modmanager.util import util

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Union
from configparser import ConfigParser
import re


#
# string formatting
#

def formatModName(name: str) -> str:
    # remove mod prefix
    if re.match('^mod.*', name, re.IGNORECASE):
        name = name[3:]
    # remove nexusmods version suffix
    lenght = len(name)
    for match in re.finditer(r'-[0-9]+-.+', name):
        lenght = match.span()[0]
    name = name[0:lenght]
    # remove file extension
    if re.search(r'. *\.(zip|rar)$', name, re.IGNORECASE):
        name = name[:-4]
    elif re.search(r'.*\.7z$', name, re.IGNORECASE):
        name = name[:-3]
    # insert spacing
    name = re.sub(r'([a-z]{2,})(?=[A-Z1-9])', r'\1 ', name)
    name = re.sub(r'([A-Z][a-z])(?=[A-Z1-9])', r'\1 ', name)
    name = re.sub(r'(_)', r' ', name)
    name = re.sub(r'([a-zA-Z])-(?=[0-9])', r'\1 ', name)
    name = re.sub(r'([0-9])-(?=[a-zA-Z])', r'\1 ', name)
    # remove leading and trailing non-alphanumeric characters
    name = re.sub(r'^[^a-zA-Z0-9]*(.*)[^a-zA-Z0-9]*$', r'\1', name)
    return name


def formatFileName(name: str, prefix: str = '') -> str:
    # remove non-alphanumeric characters
    name = re.sub(r'[^a-zA-Z0-9-_ ]', '', name)
    # join separated words and uppercase following characters
    name = re.sub(r'(?<=[a-zA-Z0-9])[-_ ]+([a-zA-Z0-9])',
                  lambda m: m.group(1).upper(), name)
    # remove trailing version
    name = re.sub(r'(v?[0-9.]+)[ ]*$', r'', name)
    # remove leading and trailing non-alphanumeric characters
    name = re.sub(r'^[^a-zA-Z0-9]*(.*)[^a-zA-Z0-9]*$', r'\1', name)
    # add prefix and capitalize
    pl = len(prefix)
    if prefix and name[:pl].lower() != prefix.lower():
        name = prefix + name[:1].upper() + name[1:]
    else:
        name = name[:pl].lower() + name[pl:pl + 1].upper() + name[pl + 1:]
    return name


#
# mod validation
#

def containsValidMod(path: Path) -> bool:
    # valid if contains a valid mod or dlc dir
    dirs = [path]
    for check in dirs:
        if check.is_dir():
            if isValidModDirectory(check) \
            or isValidDlcDirectory(check) \
            or maybeModOrDlcDirectory(check, path):
                return True
            bins = fetchBinFiles(check, onlyUngrouped=True)
            if len(bins[0]) or len(bins[1]) or len(bins[2]):
                return True
            dirs += [d for d in check.iterdir() if d.is_dir()]
    return False


def isValidModDirectory(path: Path) -> bool:
    # valid if child starts with mod and contains a non-empty content dir
    if path.is_dir() and re.match('^(mod).*', path.name, re.IGNORECASE):
        return containsContentDirectory(path)
    # TODO: enhancement: check if scripts are in it, then it's always mod
    # return path.is_dir() and containsContentDirectory(path) and containsScripts(path)
    return False


def isValidDlcDirectory(path: Path) -> bool:
    # valid if child starts with dlc and contains a non-empty content dir
    # or ends with dlc and doesn't start with mod
    if path.is_dir() and (re.match('^(dlc).*', path.name, re.IGNORECASE) \
            or re.match('^((?!mod).)*dlc$', path.name, re.IGNORECASE)):
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
    # TODO: enhancement: check if path contains scripts
    pass


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
            dirs += [d for d in check.iterdir() if d.is_dir()]
    return bins


def fetchDlcDirectories(path: Path) -> List[Path]:
    bins = []
    dirs = [path]
    for check in dirs:
        if isValidDlcDirectory(check):
            bins.append(check.relative_to(path))
        elif not isValidModDirectory(check):
            dirs += [d for d in check.iterdir() if d.is_dir()]
    return bins


def fetchUnsureDirectories(path: Path) -> List[Path]:
    bins = []
    dirs = [path]
    for check in dirs:
        if maybeModOrDlcDirectory(check, path):
            bins.append(check.relative_to(path))
        dirs += [d for d in check.iterdir() if d.is_dir() \
            and not isValidModDirectory(d) and not isValidDlcDirectory(d)]
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


@dataclass
class ContentFile:
    source: Path

    def __repr__(self) -> str:
        return '\'%s\'' % str(self.source)


@dataclass(init=False)
class Settings:
    source: Path
    config: ConfigParser

    def __init__(self, source, content):
        self.source = source
        self.config = ConfigParser(strict=False)
        self.config.optionxform = str
        self.config.read_string(content)

    def __repr__(self) -> str:
        return '\'%s\': %s' % (str(self.source), str({section: dict(self.config[section]) for section in self.config.sections()}))


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
        for file in [f for f in check.iterdir() \
                if f.is_file() and f.suffix in ('.ini', '.xml', '.txt', '.settings')]:
            relpath: Path = file.relative_to(path)

            # if the binfile is placed under bin, use its path relative to its bin dir
            if 'bin' in relpath.parts:
                minpath = Path(re.sub(r'^((?!bin\\|bin\/).)*', r'', str(relpath)))
                bins.append(BinFile(relpath, minpath))
                continue

            # otherwise guess path based on name
            if re.match(r'.+(\.xml|xml\.txt)$', relpath.name):
                # guess for input.xml
                if re.match(r'.*input([.]?part)?((\.xml)|([.]?xml\.txt))$', relpath.name):
                    bins.append(BinFile(relpath, \
                        Path('bin/config/r4game/user_config_matrix/pc/input.xml')))
                    continue
                # otherwise assume menu xml
                if re.match(r'.+\.xml', relpath.name):
                    bins.append(BinFile(relpath, \
                        Path('bin/config/r4game/user_config_matrix/pc').joinpath(relpath.name)))
                    continue

            # detect input.settings
            if re.match(r'.*input[.]?settings(\.part)?(\.txt)?$', relpath.name):
                inpu.append(InputSettings(relpath, util.readText(file)))
                continue

            # detect user.settings
            if re.match(r'.*user[.]?settings(\.part)?(\.txt)?$', relpath.name):
                user.append(UserSettings(relpath, util.readText(file)))
                continue

        dirs += [d for d in check.iterdir() if d.is_dir() and ( \
            not onlyUngrouped or \
            not isValidModDirectory(d) and \
            not isValidDlcDirectory(d) and \
            not maybeModOrDlcDirectory(d, path))]
    return (bins, user, inpu)


def fetchContentFiles(path: Path) -> List[ContentFile]:
    contents = []
    dirs = [path]
    for check in dirs:
        if check.is_dir() and check.name == 'content':
            contents.extend([ContentFile(x.relative_to(path)) for x in check.glob('**/*') if x.is_file()])
        else:
            dirs += [d for d in check.iterdir() if d.is_dir()]
    return contents


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
        key = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE', access=(winreg.KEY_READ | winreg.KEY_WOW64_64KEY))
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
        key = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE', access=(winreg.KEY_READ | winreg.KEY_WOW64_64KEY))
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
