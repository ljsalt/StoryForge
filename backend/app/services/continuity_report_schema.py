"""连续性检查报告 JSON 结构定义与校验（P4.1.3）。

设计要点：
1. 报告必须真正通过本地校验，不能只信模型自称"格式正确"。
2. 校验失败返回具体错误列表，供上层发起一次有限的修复请求。
3. 对轻微偏差做可预期归一化（severity 非法值降级为 warning、字段强制转字符串），
   但 issues 不是数组、条目不是对象、description 缺失等结构性问题一律判不合法。
"""

from __future__ import annotations

from ..database.db import CONTINUITY_OVERALL_RESULTS, CONTINUITY_SEVERITIES
from .writing_plan_schema import PlanValidationError, extract_json_object

__all__ = ["REPORT_SCHEMA", "ReportValidationError", "parse_report", "validate_report"]

# 供提示词与接口文档展示的报告结构说明
REPORT_SCHEMA = {
    "type": "object",
    "required": ["overall", "issues"],
    "properties": {
        "overall": {"enum": list(CONTINUITY_OVERALL_RESULTS)},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "severity",
                    "category",
                    "description",
                    "evidence",
                    "reference",
                    "suggestion",
                ],
                "properties": {
                    "severity": {"enum": list(CONTINUITY_SEVERITIES)},
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                    "evidence": {"type": "string"},
                    "reference": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
            },
        },
    },
}

_SEVERITY_RANK = {"info": 0, "warning": 1, "conflict": 2}
_OVERALL_RANK = {"pass": 0, "warning": 1, "conflict": 2}


class ReportValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("；".join(errors))
        self.errors = errors


def _as_text(value, field: str, errors: list[str]) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    if isinstance(value, list):
        # 容忍模型把证据写成数组：拼接为多行文本
        parts = [str(item).strip() for item in value if str(item).strip()]
        return "\n".join(parts)
    if not isinstance(value, str):
        errors.append(f"{field} 必须是字符串")
        return ""
    return value.strip()


def _normalize_issues(value, errors: list[str]) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append("issues 必须是数组")
        return []
    issues: list[dict] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            errors.append(f"issues[{index}] 必须是对象")
            continue
        description = _as_text(item.get("description"), f"issues[{index}].description", errors)
        if not description:
            errors.append(f"issues[{index}].description 不能为空")
            continue
        severity = str(item.get("severity") or "").strip().lower()
        if severity not in _SEVERITY_RANK:
            # 非法严重级别不判不合法，降级为 warning（宁多报不漏报）
            severity = "warning"
        issues.append(
            {
                "severity": severity,
                "category": _as_text(item.get("category"), f"issues[{index}].category", errors)
                or "其他",
                "description": description,
                "evidence": _as_text(item.get("evidence"), f"issues[{index}].evidence", errors),
                "reference": _as_text(
                    item.get("reference"), f"issues[{index}].reference", errors
                ),
                "suggestion": _as_text(
                    item.get("suggestion"), f"issues[{index}].suggestion", errors
                ),
            }
        )
    return issues


def _derive_overall(issues: list[dict]) -> str:
    if not issues:
        return "pass"
    worst = max(_SEVERITY_RANK[issue["severity"]] for issue in issues)
    if worst >= _SEVERITY_RANK["conflict"]:
        return "conflict"
    if worst >= _SEVERITY_RANK["warning"]:
        return "warning"
    return "pass"


def validate_report(data: dict) -> dict:
    """校验并归一化检查报告；不合法时抛出 ReportValidationError。

    overall 以模型输出为准，但与问题列表矛盾时以问题列表推导结果为准
    （例如模型说 pass 却列出 warning 问题，自动升级为 warning），
    保证「没有发现问题时也必须返回明确的检查结果」。
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        raise ReportValidationError(["检查报告必须是一个 JSON 对象"])

    issues = _normalize_issues(data.get("issues"), errors)
    if errors:
        raise ReportValidationError(errors)

    overall = str(data.get("overall") or "").strip().lower()
    derived = _derive_overall(issues)
    if overall not in CONTINUITY_OVERALL_RESULTS:
        overall = derived
    elif _OVERALL_RANK[derived] > _OVERALL_RANK[overall]:
        overall = derived

    return {"overall": overall, "issues": issues}


def parse_report(content: str) -> dict:
    """从模型输出提取并校验检查报告，统一抛 ReportValidationError。"""
    try:
        data = extract_json_object(content)
    except PlanValidationError as exc:
        raise ReportValidationError(exc.errors) from exc
    return validate_report(data)
