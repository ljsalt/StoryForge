"""API Key 加密与脱敏。

加密方案：
- 使用 Fernet（AES-128-CBC + HMAC）加密后写入 SQLite，数据库中不出现明文密钥。
- 主密钥保存在后端本地文件（默认 data/secrets/fernet.key），首次启动自动生成。
- 主密钥不通过任何 API 返回，也不提交 Git。

备份与恢复：
- 备份：复制 data/storyforge.db 与 data/secrets/fernet.key 两个文件即可。
- 恢复：将两个文件放回原位置（保持文件名与相对路径不变）。
- 只恢复数据库而丢失主密钥时，已保存的 API Key 将无法解密，需要在界面中重新填写。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings

logger = logging.getLogger(__name__)

_cached_fernet: Fernet | None = None
_cached_key_path: str | None = None


def _key_path() -> Path:
    return Path(get_settings().secret_key_file)


def _load_or_create_key() -> bytes:
    """读取主密钥；不存在时自动生成。"""
    path = _key_path()
    if path.exists():
        return path.read_bytes().strip()

    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    path.write_bytes(key)
    try:
        os.chmod(path, 0o600)
    except OSError:  # Windows 上权限位语义有限，失败不影响功能
        pass
    logger.info("已生成新的 API Key 加密主密钥：%s", path)
    return key


def get_fernet() -> Fernet:
    global _cached_fernet, _cached_key_path
    key_path = str(_key_path())
    if _cached_fernet is None or _cached_key_path != key_path:
        _cached_fernet = Fernet(_load_or_create_key())
        _cached_key_path = key_path
    return _cached_fernet


def encrypt_api_key(raw_key: str) -> str:
    return get_fernet().encrypt(raw_key.encode("utf-8")).decode("ascii")


def decrypt_api_key(token: str) -> str | None:
    """解密失败（密钥丢失或被替换）时返回 None。"""
    try:
        return get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        logger.warning("API Key 解密失败：主密钥可能已变更，请在界面重新填写密钥")
        return None


def mask_api_key(raw_key: str | None) -> str:
    """生成脱敏展示，例如 sk-****abcd。绝不返回完整密钥。"""
    if not raw_key:
        return ""
    if len(raw_key) <= 8:
        return "****"
    return f"{raw_key[:3]}****{raw_key[-4:]}"


def sanitize_text(text: str, raw_key: str | None = None) -> str:
    """清理错误信息，避免把密钥或过长响应体暴露出去。"""
    if raw_key and raw_key in text:
        text = text.replace(raw_key, "[REDACTED]")
    text = " ".join(str(text).split())
    return text[:300]
