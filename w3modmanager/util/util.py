import w3modmanager

from w3modmanager.core.errors import InvalidPathError

import asyncio
import codecs
import contextlib
import ctypes
import hashlib
import os
import re
import shutil
import subprocess
import tempfile

from collections.abc import Awaitable, Callable, Coroutine, Generator
from functools import partial, wraps
from pathlib import Path
from typing import Any
from urllib.parse import ParseResult, urlparse, urlsplit

from charset_normalizer import detect
from loguru import logger
from PySide6 import __version__ as PySide6Version


def getQtVersionString() -> str:
    return 'PySide6 ' + PySide6Version


def getVersionString() -> str:
    return w3modmanager.TITLE + ' ' + w3modmanager.VERSION


def getTitleString(title: str) -> str:
    return f'{title} ({getVersionString()})'


def getSupportedExtensions() -> list[str]:
    return ['.zip', '.rar', '.7z', '.tar', '.lzma']


def detectEncoding(path: Path) -> str:
    encoding = detect(path.read_bytes())
    if encoding['confidence'] and float(encoding['confidence']) > 0.7:
        return str(encoding['encoding'])
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
    hash_md5 = hashlib.md5(usedforsecurity=False)
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def getRuntimePath(subpath: Path | str | None) -> Path:
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


def normalizePath(path: Path, long: bool = True) -> Path:
    normalized = os.fspath(os.path.abspath(path))
    if long:
        if not normalized.startswith('\\\\?\\'):
            normalized = '\\\\?\\' + normalized
    else:
        if normalized.startswith('\\\\?\\'):
            normalized = normalized[4:]
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


def isValidModDownloadUrl(url: str) -> bool:
    url = normalizeUrl(url)
    try:
        parse = urlsplit(url, 'https')
    except ValueError:
        return False
    return parse.scheme in ['http', 'https', ''] \
        and Path(parse.path).suffix.lower() in getSupportedExtensions()


def isValidFileUrl(url: str) -> bool:
    url = normalizeUrl(url)
    try:
        parse = urlparse(url)
    except ValueError:
        return False
    return parse.scheme in ['file']


def isArchive(path: Path) -> bool:
    return os.path.isfile(path) and path.suffix.lower() in getSupportedExtensions()


def removeDirectory(path: Path) -> None:
    def getWriteAccess(func: Callable[..., Any], path: str, exc_info: Any) -> None:
        import stat
        os.chmod(path, stat.S_IWRITE)
        func(path)
    if os.path.isdir(path):
        try:
            shutil.rmtree(path, onerror=getWriteAccess)
        except OSError:
            logger.bind(path=path).error('Illegal path, could not delete')
    else:
        logger.bind(path=path).warning('Not a valid directory, could not delete')


def openDirectory(path: Path) -> None:
    if os.path.isdir(path):
        os.startfile(os.path.abspath(path), 'explore')  # noqa
    else:
        logger.bind(path=path).warning('Not a valid directory, could not open')


def openExecutable(path: Path, once: bool = False) -> None:
    path = normalizePath(path, False)
    if not os.path.isfile(path):
        logger.bind(path=path).warning('Not a valid executable, could not open')
        return
    start = True
    if once:
        try:
            from win32.win32api import OpenProcess
            from win32.win32gui import EnumWindows, GetWindow, IsIconic, SetForegroundWindow, ShowWindow
            from win32.win32process import GetModuleFileNameEx, GetWindowThreadProcessId
            existingWindows = []
            windowHandles = []
            EnumWindows(lambda windowHandle, _: windowHandles.append(windowHandle), None)
            for windowHandle in windowHandles:
                processIds = GetWindowThreadProcessId(windowHandle)
                for processId in processIds:
                    try:
                        processHandle = OpenProcess(0x1000, False, processId)
                        fileName = GetModuleFileNameEx(processHandle, 0)
                        if normalizePath(Path(fileName), False) == path:
                            existingWindows.append(windowHandle)
                    except Exception:  # noqa
                        continue
            for existingWindow in existingWindows:
                parentWindow = GetWindow(existingWindow, 4)
                if not parentWindow:
                    if IsIconic(existingWindow):
                        ShowWindow(existingWindow, 9)
                    SetForegroundWindow(existingWindow)
                    start = False
        except Exception as e:
            logger.bind(path=path).debug(f'Could not get open windows: {e}')
    if start:
        subprocess.Popen(
            [path], cwd=path.parent,  # noqa: S603
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


def scanBundleRaw(bundle: Path) -> subprocess.CompletedProcess[bytes]:
    exe = str(getRuntimePath('resources/tools/quickbms/quickbms.exe'))
    script = str(getRuntimePath('resources/tools/quickbms/witcher3.bms'))
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    CREATE_NO_WINDOW = 0x08000000
    return subprocess.run(
        [exe, '-l', script, str(bundle)],  # noqa: S603
        stdin=subprocess.DEVNULL, capture_output=True,
        creationflags=CREATE_NO_WINDOW, startupinfo=si
    )


async def scanBundle(bundle: Path) -> list[str]:
    if not os.path.isfile(bundle):
        raise InvalidPathError(bundle, 'Invalid bundle, does not exist')
    if not bundle.suffix == '.bundle':
        raise InvalidPathError(bundle, 'Invalid bundle')
    result = await asyncio.get_running_loop().run_in_executor(
        None,
        partial(scanBundleRaw, bundle)
    )
    if result.returncode != 0:
        raise InvalidPathError(
            bundle,
            result.stderr.decode('utf-8') if result.stderr else 'Could not read bundle'
        )
    output: str = result.stdout.decode('utf-8')
    files = []
    for line in output.splitlines():
        space = line.rfind(' ')
        files.append(line[space + 1 if space else 0:])
    return files


def extractArchive(archive: Path, target: Path) -> None:
    if os.path.exists(target):
        removeDirectory(target)
    target.mkdir(parents=True)
    exe = str(getRuntimePath('resources/tools/7zip/7z.exe'))
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    CREATE_NO_WINDOW = 0x08000000
    result: subprocess.CompletedProcess[bytes] = subprocess.run(
        [exe, 'x', str(archive), '-o' + '' + str(target) + '', '-y'],  # noqa: S603
        stdin=subprocess.DEVNULL, capture_output=True,
        creationflags=CREATE_NO_WINDOW, startupinfo=si
    )
    if result.returncode != 0:
        raise InvalidPathError(
            archive,
            result.stderr.decode('utf-8') if result.stderr else 'Could not extract archive'
        )


async def extractMod(archive: Path) -> Path:
    if not isArchive(archive):
        raise InvalidPathError(archive, 'Invalid archive')
    target = Path(tempfile.gettempdir()).joinpath('w3modmanager/cache').joinpath(f'.{archive.stem}')
    target = normalizePath(target)
    await asyncio.get_running_loop().run_in_executor(
        None,
        partial(extractArchive, archive, target)
    )
    return target


def createAsyncTask(coro: Generator[Any, Any, Any] | Coroutine[Any, Any, Any], refset: set[Any]) -> asyncio.Task[Any]:
    """Create an async task and add it to a reference set to prevent it from being garbage collected"""
    task = asyncio.create_task(coro)
    refset.add(task)
    task.add_done_callback(refset.discard)
    return task


def debounce(ms: int, cancel_running: bool = False) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Any]]:
    """Debounce a functions execution by {ms} milliseconds"""
    def decorator(fun: Callable[..., Awaitable[Any]]) -> Callable[..., Any]:

        @wraps(fun)
        def debounced(*args: Any, **kwargs: Any) -> Awaitable[Any]:
            debounced.__debounced = set()  # type: ignore

            def deferred() -> None:
                async def internal() -> None:
                    try:
                        await fun(*args, **kwargs)
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.exception(str(e))
                task = createAsyncTask(internal(), debounced.__debounced)  # type: ignore
                if cancel_running:
                    try:
                        if not debounced.task.done():  # type: ignore
                            debounced.task.cancel()  # type: ignore
                    except AttributeError:
                        pass
                debounced.task = task  # type: ignore
            with contextlib.suppress(AttributeError):
                debounced.timer.cancel()  # type: ignore

            debounced.timer = asyncio.get_running_loop().call_later(ms / 1000.0, deferred)  # type: ignore
            return debounced.timer  # type: ignore

        def cancel() -> bool:
            try:
                debounced.timer.cancel()  # type: ignore
                debounced.task.cancel()  # type: ignore
                return True
            except AttributeError:
                return False

        debounced.cancel = cancel  # type: ignore
        return debounced
    return decorator
