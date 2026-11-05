"""P4.1.1 补充验收：AI 任务异常恢复测试。

验证：
1. 服务重启后遗留的 running 记录被明确标记失败（interrupted_by_restart）。
2. 超过阈值仍 running 的记录被惰性回收（stale_timeout）。
3. 真实执行中的新任务不被误判。
4. 已结束的记录不受影响。
"""

from datetime import datetime, timedelta, timezone

from app.database.db import get_connection
from app.services import ai_task_service


def _create_novel(client):
    r = client.post("/api/novels", json={"title": "任务恢复小说"})
    assert r.status_code == 200
    return r.json()


def _assign_started_at(task_id: str, minutes_ago: int, status: str = "running") -> None:
    stamp = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat(
        timespec="seconds"
    )
    with get_connection() as conn:
        # heartbeat_at 是回收判断的首选依据，模拟"长时间无心跳"时必须一并回拨
        conn.execute(
            "UPDATE ai_generation_tasks SET status = ?, started_at = ?, heartbeat_at = ? WHERE id = ?",
            (status, stamp, stamp, task_id),
        )


def _start_raw_task(novel_id: str) -> str:
    return ai_task_service.create_task(
        novel_id=novel_id,
        task_type="writer",
        model_id=None,
        model_identifier="test-model",
        provider_id=None,
        prompt_template_id=None,
        template_version=None,
        input_summary="原始任务",
        estimated_tokens=10,
    )


def test_interrupt_running_tasks_on_restart(client):
    novel = _create_novel(client)
    task_id = _start_raw_task(novel["id"])
    # 启动时没有任何调用可能真实执行：全部视为中断
    assert ai_task_service.interrupt_running_tasks() >= 1

    task = client.get(
        f"/api/ai/tasks/{task_id}", params={"novel_id": novel["id"]}
    ).json()
    assert task["status"] == "failed"
    assert task["error_code"] == "interrupted_by_restart"
    assert task["completed_at"]
    assert task["error_message"]


def test_stale_running_reaped_but_fresh_kept(client):
    novel = _create_novel(client)
    stale_id = _start_raw_task(novel["id"])
    fresh_id = _start_raw_task(novel["id"])
    _assign_started_at(stale_id, 120)  # 2 小时前，明显异常遗留
    _assign_started_at(fresh_id, 0)    # 刚启动，属于真实执行中

    tasks = client.get("/api/ai/tasks", params={"novel_id": novel["id"]}).json()
    by_id = {t["id"]: t for t in tasks}
    assert by_id[stale_id]["status"] == "failed"
    assert by_id[stale_id]["error_code"] == "stale_timeout"
    # 新建任务不被误杀
    assert by_id[fresh_id]["status"] == "running"

    # 边界：略小于阈值不被回收
    _assign_started_at(fresh_id, 10)
    tasks2 = client.get("/api/ai/tasks", params={"novel_id": novel["id"]}).json()
    assert {t["id"]: t for t in tasks2}[fresh_id]["status"] == "running"

    # 超过阈值后被回收
    _assign_started_at(fresh_id, 16)
    tasks3 = client.get("/api/ai/tasks", params={"novel_id": novel["id"]}).json()
    assert {t["id"]: t for t in tasks3}[fresh_id]["status"] == "failed"


def test_completed_and_failed_tasks_untouched(client, monkeypatch):
    novel = _create_novel(client)
    task_id = _start_raw_task(novel["id"])
    ai_task_service.complete_task(
        task_id,
        output_summary="已完成",
        input_tokens=5,
        output_tokens=6,
        truncated=False,
        latency_ms=100,
    )
    _assign_started_at(task_id, 300, status="completed")
    count = ai_task_service.reap_stale_tasks()
    assert count == 0
    task = client.get(
        f"/api/ai/tasks/{task_id}", params={"novel_id": novel["id"]}
    ).json()
    assert task["status"] == "completed"
    assert task["output_tokens"] == 6


def test_reap_is_idempotent(client):
    novel = _create_novel(client)
    task_id = _start_raw_task(novel["id"])
    _assign_started_at(task_id, 120)
    assert ai_task_service.reap_stale_tasks() == 1
    # 第二次不再重复处理
    assert ai_task_service.reap_stale_tasks() == 0
    task = client.get(
        f"/api/ai/tasks/{task_id}", params={"novel_id": novel["id"]}
    ).json()
    assert task["status"] == "failed"
    assert task["error_code"] == "stale_timeout"
