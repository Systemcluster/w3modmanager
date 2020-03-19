from typing import Any

from httpx import AsyncClient  # noqa


baseUrl = f'https://api.nexusmods.com/v1'
userUrl = f'{baseUrl}/users'
gameUrl = f'{baseUrl}/games/witcher3'

timeout = 1


async def getUserInformation(session: AsyncClient, apikey: str) -> Any:
    if not apikey:
        return None
    user = await session.get(f'{userUrl}/validate.json', headers={'apikey': apikey}, timeout=timeout)
    if user.status_code != 200:
        return None
    return user.json()

