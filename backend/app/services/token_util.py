"""Token 估算工具。

当前没有可靠的本地 Tokenizer，这里采用保守估算：
- 中日韩字符（含常用中文标点）按 1 token / 字；
- 其余字符（英文、数字、符号）按约 4 字符 / token。

所有估算结果都应标记为 estimated，不得伪装成精确计费。
"""

from __future__ import annotations


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    if 0x2E80 <= code <= 0x9FFF or 0xF900 <= code <= 0xFAFF:
        return True
    # 常用全角标点
    return 0x3000 <= code <= 0x303F or 0xFF00 <= code <= 0xFF65


def estimate_tokens(text: str) -> int:
    """保守估算文本 token 数（估算值，非精确值）。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if _is_cjk(ch))
    other = len(text) - cjk
    # 英文等按 4 字符一个 token 估算，至少把零头算进来
    return cjk + (other + 3) // 4
