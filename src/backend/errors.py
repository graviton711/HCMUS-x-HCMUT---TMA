"""Backend errors. Transport maps `AppError` to `{error: {code, message}}`."""


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable

    def payload(self) -> dict[str, dict[str, str]]:
        return {"error": {"code": self.code, "message": self.message}}
