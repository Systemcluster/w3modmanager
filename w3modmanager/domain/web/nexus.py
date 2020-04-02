from __future__ import annotations

import w3modmanager

from typing import Any, Optional
import platform

from httpx import AsyncClient, HTTPError, Response
from qtpy.QtCore import QSettings
from asyncqt import asyncClose  # noqa
from loguru import logger


__baseUrl = 'https://api.nexusmods.com'
__userUrl = '/v1/users'
__modsUrl = '/v1/games/witcher3/mods'

__session: Optional[AsyncClient] = None


class RequestError(HTTPError):
    pass


class NoAPIKeyError(Exception):
    pass


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


async def getUserInformation(apikey: str) -> Any:
    if not apikey:
        return None
    try:
        user: Response = await getSession().get(
            f'{__userUrl}/validate.json', headers={'apikey': apikey.encode('ascii', 'backslashreplace')},
            timeout=5.0
        )
    except HTTPError as e:
        logger.warning(f'Could not get user information: {type(e).__name__}')
        raise RequestError(request=e.request, response=e.response)
    if user.status_code == 429:
        logger.warning(f'Could not get user information: Request limit reached')
    if user.status_code != 200:
        return None
    return user.json()


async def getModInformation(md5hash: str) -> Any:
    settings = QSettings()
    apikey = settings.value('nexusAPIKey', '')
    if not apikey:
        logger.warning(f'Could not get mod information: No API Key')
        raise NoAPIKeyError()
    try:
        info: Response = await getSession().get(
            f'{__modsUrl}/md5_search/{md5hash}.json',
            headers={'apikey': apikey.encode('ascii', 'backslashreplace')},
            timeout=5.0
        )
    except HTTPError as e:
        logger.warning(f'Could not get mod information: {type(e).__name__}')
        raise RequestError(request=e.request, response=e.response)
    if info.status_code == 429:
        logger.warning(f'Could not get mod information: Request limit reached')
    if info.status_code == 404:
        logger.warning(f'Could not get mod information: No file with hash {md5hash} found')
    if info.status_code != 200:
        return None
    return info.json()


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
