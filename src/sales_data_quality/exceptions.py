class DataQualityError(Exception):
    """利用者に安全に表示できる業務例外。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
