from __future__ import annotations


from typing import Any, Optional

from httpx import AsyncClient, HTTPError  # noqa
from asyncqt import asyncClose  # noqa
from loguru import logger


__baseUrl = 'https://api.nexusmods.com'
__userUrl = '/v1/users'
__gameUrl = '/v1/games/witcher3'
__modsUrl = '/v1/mods'

__session: Optional[AsyncClient] = None


class RequestError(HTTPError):
    pass


def getSession() -> AsyncClient:
    global __session
    if not __session:
        __session = AsyncClient(base_url=__baseUrl)
    return __session


async def getUserInformation(apikey: str) -> Any:
    if not apikey:
        return None
    try:
        user = await getSession().get(f'{__userUrl}/validate.json', headers={'apikey': apikey}, timeout=5.0)
    except HTTPError as e:
        logger.exception(f'{str(e)}')
        raise RequestError(request=e.request, response=e.response)
    if user.status_code != 200:
        return None
    return user.json()

