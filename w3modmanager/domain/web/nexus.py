from __future__ import annotations

import w3modmanager
from w3modmanager.util.util import isValidNexusModsUrl, normalizeUrl

from typing import Optional
from urllib.parse import urlsplit
import platform
import re
from pathlib import Path
import asyncio
from functools import partial

from httpx import AsyncClient, HTTPError, HTTPStatusError, RequestError as HTTPXRequestError, Response, Request, stream
from PySide6.QtCore import QSettings
from loguru import logger


__baseUrl = 'https://api.nexusmods.com'
__userUrl = '/v1/users'
__modsUrl = '/v1/games/witcher3/mods'

__session: Optional[AsyncClient] = None


class RequestError(HTTPXRequestError):
    def __init__(self, kind: str, request: Request = None, response: Response = None) -> None:
        super().__init__(request=request, message=kind)

        self.response = response
        self.kind = kind

    def __str__(self) -> str:
        return f'{self.response}' if self.response else f'{self.kind}'


class ResponseError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class UnauthorizedError(ResponseError):
    def __init__(self, message: str = 'Unauthorized') -> None:
        super().__init__(message)


class NoAPIKeyError(UnauthorizedError):
    def __init__(self, message: str = 'No Nexus Mods API Key configured') -> None:
        super().__init__(message)


class NoPremiumMembershipException(UnauthorizedError):
    def __init__(self, message: str = 'Nexus Mods premium membership required') -> None:
        super().__init__(message)


class RequestLimitReachedError(ResponseError):
    def __init__(self, message: str = 'Request limit reached') -> None:
        super().__init__(message)


class NotFoundError(ResponseError):
    def __init__(self, message: str = 'Not found') -> None:
        super().__init__(message)


class ResponseContentError(ResponseError):
    def __init__(self, message: str = 'Wrong response content') -> None:
        super().__init__(message)


async def closeSession() -> None:
    global __session
    if __session:
        await __session.aclose()


def getSession() -> AsyncClient:
    global __session
    if not __session:
        useragent = f'{w3modmanager.NAME}/{w3modmanager.VERSION} ' \
            f'({platform.system()} {platform.version()}; {platform.machine()})'
        __session = AsyncClient(
            base_url=__baseUrl,
            headers={'User-Agent': useragent}
        )
    return __session


def getModId(url: str) -> int:
    if not isValidNexusModsUrl(url):
        return 0
    url = normalizeUrl(url)
    try:
        parse = urlsplit(url, 'https')
    except ValueError:
        return 0
    match = re.match(r'^/witcher3/mods/([0-9]+)', parse.path)
    if not match or not match.group(1) or not match.group(1).isdigit():
        return 0
    return int(match.group(1))


async def getUserInformation(apikey: str) -> dict:
    if not apikey:
        raise NoAPIKeyError()
    try:
        user: Response = await getSession().get(
            f'{__userUrl}/validate.json', headers={
                'apikey'.encode('ascii'): apikey.strip().encode('ascii', 'backslashreplace')},
            timeout=5.0
        )
    except HTTPStatusError as e:
        raise RequestError(request=e.request, response=e.response, kind=str(e))
    except HTTPXRequestError as e:
        raise RequestError(request=e.request, response=None, kind=str(e))
    except HTTPError as e:
        raise RequestError(request=None, response=None, kind=str(e))
    if user.status_code == 429:
        raise RequestLimitReachedError()
    if user.status_code == 404:
        raise NotFoundError()
    if user.status_code == 401:
        raise UnauthorizedError()
    if user.status_code != 200:
        raise ResponseError(f'Unexpected response: Status {user.status_code}')
    json = user.json()
    if not isinstance(json, dict):
        raise ResponseContentError(f'Unexpected response: expected dict, got {type(json).__name__}')
    return json


async def getModInformation(md5hash: str) -> list:
    settings = QSettings()
    apikey = str(settings.value('nexusAPIKey', ''))
    if not apikey:
        raise NoAPIKeyError()
    try:
        info: Response = await getSession().get(
            f'{__modsUrl}/md5_search/{md5hash}.json',
            headers={
                'apikey'.encode('ascii'): apikey.strip().encode('ascii', 'backslashreplace')},
            timeout=5.0
        )
    except HTTPStatusError as e:
        raise RequestError(request=e.request, response=e.response, kind=str(e))
    except HTTPXRequestError as e:
        raise RequestError(request=e.request, response=None, kind=str(e))
    except HTTPError as e:
        raise RequestError(request=None, response=None, kind=str(e))
    if info.status_code == 429:
        raise RequestLimitReachedError()
    if info.status_code == 404:
        raise NotFoundError(f'No file with hash {md5hash} found')
    if info.status_code == 401:
        raise UnauthorizedError()
    if info.status_code != 200:
        raise ResponseError(f'Unexpected response: Status {info.status_code}')
    json = info.json()
    if not isinstance(json, list):
        raise ResponseContentError(f'Unexpected response: expected list, got {type(json).__name__}')
    return json


async def getModFiles(modid: int) -> dict:
    settings = QSettings()
    apikey = str(settings.value('nexusAPIKey', ''))
    if not apikey:
        raise NoAPIKeyError()
    try:
        files: Response = await getSession().get(
            f'{__modsUrl}/{modid}/files.json',
            headers={
                'apikey'.encode('ascii'): apikey.strip().encode('ascii', 'backslashreplace')},
            timeout=5.0
        )
    except HTTPStatusError as e:
        raise RequestError(request=e.request, response=e.response, kind=str(e))
    except HTTPXRequestError as e:
        raise RequestError(request=e.request, response=None, kind=str(e))
    except HTTPError as e:
        raise RequestError(request=None, response=None, kind=str(e))
    if files.status_code == 429:
        raise RequestLimitReachedError()
    if files.status_code == 404:
        raise NotFoundError(f'No mod with id {modid} found')
    if files.status_code == 403:
        raise NoPremiumMembershipException()
    if files.status_code == 401:
        raise UnauthorizedError()
    if files.status_code != 200:
        raise ResponseError(f'Unexpected response: Status {files.status_code}')
    json = files.json()
    if not isinstance(json, dict):
        raise ResponseContentError(f'Unexpected response: expected list, got {type(json).__name__}')
    return json


async def getModFileUrls(modid: int, fileid: int) -> list:
    settings = QSettings()
    apikey = str(settings.value('nexusAPIKey', ''))
    if not apikey:
        raise NoAPIKeyError()
    try:
        files: Response = await getSession().get(
            f'{__modsUrl}/{modid}/files/{fileid}/download_link.json',
            headers={
                'apikey'.encode('ascii'): apikey.strip().encode('ascii', 'backslashreplace')},
            timeout=5.0
        )
    except HTTPStatusError as e:
        raise RequestError(request=e.request, response=e.response, kind=str(e))
    except HTTPXRequestError as e:
        raise RequestError(request=e.request, response=None, kind=str(e))
    except HTTPError as e:
        raise RequestError(request=None, response=None, kind=str(e))
    if files.status_code == 429:
        raise RequestLimitReachedError()
    if files.status_code == 404:
        raise NotFoundError(f'No mod with id {modid} found')
    if files.status_code == 403:
        raise NoPremiumMembershipException()
    if files.status_code == 401:
        raise UnauthorizedError()
    if files.status_code != 200:
        raise ResponseError(f'Unexpected response: Status {files.status_code}')
    json = files.json()
    if not isinstance(json, list):
        raise ResponseContentError(f'Unexpected response: expected list, got {type(json).__name__}')
    return json


async def downloadFile(url: str, target: Path) -> None:
    settings = QSettings()
    apikey = settings.value('nexusAPIKey', '')
    if not apikey:
        raise NoAPIKeyError()
    await asyncio.get_running_loop().run_in_executor(
        None,
        partial(downloadFileSync, url, target, apikey)
    )


def downloadFileSync(url: str, target: Path, apikey: str) -> None:
    try:
        with target.open('wb') as file:
            with stream(
                'GET',
                url,
                headers={
                'apikey'.encode('ascii'): apikey.strip().encode('ascii', 'backslashreplace')},
                timeout=250.0
            ) as download:
                if download.status_code == 429:
                    raise RequestLimitReachedError()
                if download.status_code == 404:
                    raise NotFoundError(f'No file with URL {url} found')
                if download.status_code == 403:
                    raise NoPremiumMembershipException()
                if download.status_code == 401:
                    raise UnauthorizedError()
                if download.status_code != 200:
                    raise ResponseError(f'Unexpected response: Status {download.status_code}')
                for data in download.iter_bytes():
                    file.write(data)
    except HTTPStatusError as e:
        raise RequestError(request=e.request, response=e.response, kind=str(e))
    except HTTPXRequestError as e:
        raise RequestError(request=e.request, response=None, kind=str(e))
    except HTTPError as e:
        raise RequestError(request=None, response=None, kind=str(e))


def getCategoryName(categoryid: int) -> str:
    try:
        return __modCategories[categoryid]
    except KeyError as e:
        logger.debug(f'Unknown category: {str(e)}')
    return ''


# mod categories from nexusmods.com/witcher3/mods/categories
__modCategories = {
    1: 'The Witcher 3',
    2: 'Miscellaneous',
    3: 'Controller Button Layout',
    4: 'Visuals and Graphics',
    5: 'Skills and Leveling',
    6: 'User Interface',
    8: 'Tweaks',
    10: 'Armour',
    11: 'Cheats and God items',
    12: 'Bug Fixes',
    13: 'Combat',
    14: 'Gwent',
    15: 'Modders Resources and Tutorials',
    16: 'ReShade Preset',
    17: 'Gameplay Changes',
    18: 'Models and Textures',
    19: 'Weapons',
    20: 'Signs',
    21: 'Save Games',
    22: 'Overhaul',
    23: 'Characters',
    24: 'Items',
    25: 'Camera',
    27: 'Debug Console',
    28: 'Alchemy and Crafting',
    29: 'Weapons and Armour',
    30: 'Inventory',
    31: 'Balancing',
    32: 'Immersion',
    33: 'Utilities',
    35: 'Audio - Music',
    36: 'Audio - Voice',
    37: 'Audio - SFX',
    40: 'Performance',
    41: 'Hair and Face',
    42: 'Quests and Adventures',
}
