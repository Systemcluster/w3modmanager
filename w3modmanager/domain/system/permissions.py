"""System permission queries and modifications"""

from w3modmanager.util.util import getWindowsPath

import os
import platform
import shutil
import subprocess

from pathlib import Path

from loguru import logger


def getWritePermissions(path: Path, children: bool = True) -> bool:
    """Check user write permissions to directory"""
    system = platform.system()
    try:
        if system == 'Windows':
            import pywintypes  # type: ignore # noqa
            import win32api  # type: ignore
            import win32security  # type: ignore

            if children:
                # only check the top level directories for performance reasons
                # this should be enough in most cases
                dirs = [path.resolve(strict=True), *list(path.glob('*'))]
            else:
                dirs = [path.resolve(strict=True)]
            for file in dirs:
                user = win32api.GetUserName()
                usid = win32security.ConvertSidToStringSid(win32security.LookupAccountName(None, user)[0])
                info = win32security.GetFileSecurity(str(file), win32security.DACL_SECURITY_INFORMATION)
                dacl = info.GetSecurityDescriptorDacl()
                expl = dacl.GetExplicitEntriesFromAcl()
                # if no explicit access is set, assume inherited access
                if not expl:
                    if file.parent not in dirs:
                        dirs.append(file.parent)
                    continue
                # search for a permission set with full access or modify access
                # for the current user or for authenticated users
                good = False
                for perm in expl:
                    dsid = win32security.ConvertSidToStringSid(perm['Trustee']['Identifier'])  # type: ignore
                    dacc = perm['AccessPermissions']
                    if dsid in (usid, 'S-1-5-11',) and dacc in (0x1f01ff, 0x1301bf,):
                        good = True
                        break
                if not good:
                    return False
            return True
        else:
            if children:
                # only check the top level entries for performance reasons
                dirs = [path.resolve(strict=True), *list(path.glob('*'))]
            else:
                dirs = [path.resolve(strict=True)]
            return all(os.access(file, os.W_OK) for file in dirs)
    except Exception as e:
        logger.exception(str(e))
        return False


def setWritePermissions(path: Path) -> bool:
    """Set write permissions to directory for current user"""
    system = platform.system()
    try:
        if system == 'Windows':
            import pywintypes  # type: ignore # noqa
            import win32api  # type: ignore

            # get the paths to the required system executables
            icacls = shutil.which('icacls.exe') \
                or getWindowsPath().joinpath('system32/icacls.exe')
            powershell = shutil.which('powershell.exe') or shutil.which('pwsh.exe') \
                or getWindowsPath().joinpath('WindowsPowerShell/v1.0/powershell.exe')
            # add modify access permissions for the current user
            # the indirection through powershell allows access through the uac screen
            user = win32api.GetUserName()
            si = subprocess.STARTUPINFO()  # type: ignore
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore
            CREATE_NO_WINDOW = 0x08000000
            result = subprocess.run([  # noqa
                f'{Path(powershell).resolve(strict=True)!s}', '-Command',
                f'Start-Process \
                    -FilePath "{Path(icacls).resolve(strict=True)!s}" \
                    -ArgumentList \'"{path.resolve(strict=True)!s}" "/grant" "{user}:(OI)(CI)M" "/T"\' \
                    -Verb RunAs -WindowStyle Hidden'],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW, startupinfo=si)
            return result.returncode == 0
        elif system == 'Darwin':
            # add write permissions for the current user
            # the indirection through osascript allows access through an auth dialog
            resolved = str(path.resolve(strict=True))
            osascript = shutil.which('osascript')
            if not osascript:
                return True
            script = '''
                on run argv
                    set posixPath to item 1 of argv
                    do shell script "chmod -R u+w " & quoted form of posixPath with administrator privileges
                end run
            '''
            result = subprocess.run(  # noqa: S603
                [osascript, '-e', script, resolved],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False)
            return result.returncode == 0
        elif system == 'Linux':
            # add write permissions for the current user
            # the indirection through pkexec allows access through an auth dialog
            resolved = str(path.resolve(strict=True))
            pkexec = shutil.which('pkexec')
            if not pkexec:
                return True
            result = subprocess.run(  # noqa: S603
                [pkexec, 'chmod', '-R', 'u+w', resolved],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False)
            return result.returncode == 0
        else:
            return True
    except Exception as e:
        logger.exception(str(e))
        return False
