import w3modmanager

import codecs
import re
import hashlib
import shutil
import tempfile
import ctypes
import os
import asyncio
from pathlib import Path
from urllib.parse import urlparse, urlsplit, ParseResult
from typing import Union, List
from functools import wraps

import cchardet
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
    return w3modmanager.TITLE + ' ' + w3modmanager.VERSION


def getTitleString(title: str) -> str:
    return '%s (%s)' % (title, getVersionString())


def getSupportedExtensions() -> List[str]:
    return ['.zip', '.rar', '.7z', '.tar', '.lzma']


def detectEncoding(path: Path) -> str:
    encoding = cchardet.detect(path.read_bytes())
    if encoding['confidence'] > 0.7:
        return encoding['encoding']
    return 'utf-8'


def readText(path: Path) -> str:
    b = path.read_bytes()
    if b.startswith(codecs.BOM_UTF16_LE):
        return path.read_text(encoding='utf-16')
    if b.startswith(codecs.BOM_UTF16_BE):
        return path.read_text(encoding='utf-16')
    if b.startswith(codecs.BOM_UTF16):
        return path.read_text(encoding='utf-16')
    return path.read_text(encoding=detectEncoding(path))


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
    from ctypes import windll, wintypes
    CSIDL_PERSONAL = 5       # user documents
    SHGFP_TYPE_CURRENT = 0   # get current, not default value
    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
    return Path(buf.value)


def getWindowsPath() -> Path:
    from ctypes import windll
    windows_directory_buffer = ctypes.create_unicode_buffer(1024)
    if not windll.kernel32.GetWindowsDirectoryW(windows_directory_buffer, 1024):
        return Path(os.environ['WINDIR'])
    else:
        return Path(windows_directory_buffer.value)


def removeUrlScheme(url: str) -> str:
    return ParseResult('', *urlparse(url)[1:]).geturl()[2:]


def normalizeUrl(url: str) -> str:
    if '//' not in url:
        url = f'//{url}'
    return url


def normalizePath(path: Path):
    normalized = os.fspath(path.resolve())
    if not normalized.startswith('\\\\?\\'):
        normalized = '\\\\?\\' + normalized
    return Path(normalized)


def isValidNexusModsUrl(url: str) -> bool:
    url = normalizeUrl(url)
    try:
        parse = urlsplit(url, 'https')
    except ValueError:
        return False
    return parse.scheme in ['http', 'https', ''] \
        and bool(re.match(r'^(www\.)?nexusmods.com', parse.netloc)) \
        and bool(re.match(r'^/witcher3/mods/[0-9]+', parse.path))


def isValidFileUrl(url: str) -> bool:
    url = normalizeUrl(url)
    parse = urlparse(url)
    return parse.scheme in ['file']


def isArchive(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in getSupportedExtensions()


def removeDirectory(path: Path):
    def getWriteAccess(func, path, exc_info):
        import stat
        os.chmod(path, stat.S_IWRITE)
        func(path)
    shutil.rmtree(path, onerror=getWriteAccess)


async def extractArchive(archive: Path, target: Path) -> Path:
    if target.exists():
        removeDirectory(target)
    target.mkdir(parents=True)
    exe = str(getRuntimePath('tools/7zip/7z.exe'))
    process = await asyncio.create_subprocess_shell(
        exe + ' x "' + str(archive) + '" -o"' + str(target) + '"',
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise InvalidPathError(
            archive,
            stdout.decode().strip() if stderr else 'Could not extract archive')
    return target


async def extractMod(archive: Path) -> Path:
    if not isArchive(archive):
        raise InvalidPathError(archive, 'Invalid archive')
    target = Path(tempfile.gettempdir()).joinpath('w3modmanager/cache').joinpath(f'.{archive.stem}')
    target = normalizePath(target)
    await extractArchive(archive, target)
    return target


def debounce(ms: int):
    """Debounce a functions execution by {ms} milliseconds"""
    def decorator(fun):
        @wraps(fun)
        def debounced(*args, **kwargs):
            def deferred():
                asyncio.get_running_loop().create_task(fun(*args, **kwargs))
            try:
                debounced.timer.cancel()
            except AttributeError:
                pass
            debounced.timer = asyncio.get_running_loop().call_later(ms / 1000.0, deferred)
        return debounced
    return decorator
