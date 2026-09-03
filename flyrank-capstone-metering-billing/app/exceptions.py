class QuotaExceededError(Exception):
    def __init__(self, message: str, status_code: int = 429):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
