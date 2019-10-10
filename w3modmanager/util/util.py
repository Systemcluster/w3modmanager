import w3modmanager

import codecs
import re
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlsplit, ParseResult
from typing import Union

from qtpy import API_NAME, QT_VERSION


class InvalidPathError(IOError):
    def __init__(self, path: Path, message: str = ''):
        super().__init__(f'{f"{message}: " if message else ""}{str(path.resolve())}')
        self.path = path
        self.message = message


class UnexpectedInputError(IOError):
    def __init__(self, path: Path, message: str = ''):
        super().__init__(f'{f"{message}: " if message else ""}{str(path.resolve())}')
        self.path = path
        self.message = message


def getQtVersionString() -> str:
    return API_NAME + ' ' + QT_VERSION


def getVersionString() -> str:
    return w3modmanager.TITLE + ' ' + w3modmanager.__version__


def getTitleString(title: str) -> str:
    return '%s (%s)' % (title, getVersionString())


def readText(path: Path) -> str:
    b = path.read_bytes()
    if b.startswith(codecs.BOM_UTF16_LE):
        return path.read_text(encoding='utf-16')
    if b.startswith(codecs.BOM_UTF16_BE):
        return path.read_text(encoding='utf-16')
    if b.startswith(codecs.BOM_UTF16):
        return path.read_text(encoding='utf-16')
    return path.read_text()


def getMD5Hash(path: Path) -> str:
    hash_md5 = hashlib.md5()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def getRuntimePath(subpath: Union[Path, str, None]) -> Path:
    if subpath:
        return Path(w3modmanager.__file__).parent.parent.joinpath(subpath).resolve()
    else:
        return Path(w3modmanager.__file__).parent.parent.resolve()


def getUserDocumentsPath() -> Path:
    import ctypes.wintypes
    CSIDL_PERSONAL = 5       # user documents
    SHGFP_TYPE_CURRENT = 0   # get current, not default value
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
    return Path(buf.value)


def removeUrlScheme(url: str) -> str:
    return ParseResult('', *urlparse(url)[1:]).geturl()[2:]


def normalizeUrl(url: str) -> str:
    if '//' not in url:
        url = f'//{url}'
    return url


def isValidNexusModsUrl(url: str) -> bool:
    url = normalizeUrl(url)
    parse = urlsplit(url, 'https')
    return parse.scheme in ['http', 'https', ''] \
        and bool(re.match(r'^(www\.)?nexusmods.com', parse.netloc)) \
        and bool(re.match(r'^/witcher3/mods/[0-9]+', parse.path))


def isValidFileUrl(url: str) -> bool:
    url = normalizeUrl(url)
    parse = urlparse(url)
    return parse.scheme in ['file']


def isArchive(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in (
        '.zip', '.rar', '.7z', '.tar', '.lzma')


def extractArchive(archive: Path, target: Path) -> Path:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    exe = str(getRuntimePath('tools/7zip/7z.exe'))
    result: subprocess.CompletedProcess = subprocess.run(
        exe + ' x "' + str(archive) + '" -o"' + str(target) + '"',
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if result.returncode != 0:
        raise InvalidPathError(
            archive,
            result.stderr if result.stderr else 'Could not extract archive')
    return target


def extractMod(archive: Path) -> Path:
    if not isArchive(archive):
        raise InvalidPathError(archive, 'Invalid archive')
    target = Path(tempfile.gettempdir()).joinpath('w3modmanager/mod').joinpath(archive.stem)
    extractArchive(archive, target)
    return target
