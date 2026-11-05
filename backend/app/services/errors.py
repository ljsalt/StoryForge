"""服务层统一业务异常。"""

from __future__ import annotations


class ServiceError(Exception):
    """业务错误，携带 HTTP 状态码与中文提示。"""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
