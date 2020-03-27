from pathlib import Path


#
# util errors
#


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


#
# model errors
#


class ModelError(IOError):
    def __init__(self, path: Path):
        super().__init__(f'{self.message}: \'{str(path.resolve())}\'')
        self.path = path
    message = 'Model Error'


class OtherInstanceError(ModelError):
    message = 'Could not lock'


class InvalidGamePath(ModelError):
    message = 'Invalid game path'


class InvalidConfigPath(ModelError):
    message = 'Invalid config path'


class InvalidCachePath(ModelError):
    message = 'Invalid cache path'


#
# mod errors
#


class ModError(ValueError):
    pass


class ModExistsError(ModError):
    def __init__(self, filename: str, target: str):
        super().__init__(f'Mod already exists: {target}/{filename}')


class ModNotFoundError(ModError):
    def __init__(self, filename: str, target: str):
        super().__init__(f'Mod not found: {target}/{filename}')
