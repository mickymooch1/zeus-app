"""
scheduler.py — APScheduler wrapper for Zeus scheduled tasks.

Uses AsyncIOScheduler so all jobs run as coroutines in FastAPI's event loop.
No thread pool is involved for async job functions, making concurrent SQLite
writes safe under WAL mode.

Public interface:
    init_scheduler(history_store)  — call in FastAPI lifespan startup
    shutdown_scheduler()           — call in FastAPI lifespan teardown
    add_job(task)                  — call after POST /scheduled-tasks
    remove_job(task_id)            — call after DELETE /scheduled-tasks/{id}
    set_job_enabled(task_id, active) — call after PATCH toggle
    compute_next_run(cron_expression) — returns next fire time as ISO string
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger("zeus.scheduler")

_scheduler = None
_history = None  # set by init_scheduler; used by _run_scheduled_task


def compute_next_run(cron_expression: str) -> str:
    """Return the next fire time for a cron expression as an ISO datetime string (UTC)."""
    from croniter import croniter
    now = datetime.now(timezone.utc)
    return croniter(cron_expression, now).get_next(datetime).isoformat()


def init_scheduler(history_store) -> None:
    """Start the AsyncIOScheduler and load all active jobs from the DB."""
    global _scheduler, _history
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    import db

    _history = history_store
    _scheduler = AsyncIOScheduler()
    _scheduler.start()
    log.info("Scheduler started")

    db_path = db.get_db_path()
    tasks = db.get_all_active_scheduled_tasks(db_path)
    for task in tasks:
        add_job(task)
    log.info("Scheduler loaded %d active job(s) from DB", len(tasks))


def shutdown_scheduler() -> None:
    """Stop the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler shut down")
    _scheduler = None


def add_job(task: dict) -> None:
    """Add an APScheduler cron job for the given task dict."""
    if _scheduler is None:
        return
    from apscheduler.triggers.cron import CronTrigger

    task_id = task["id"]
    cron = task["cron_expression"]

    # Remove existing job with the same ID before adding (idempotent)
    if _scheduler.get_job(task_id):
        _scheduler.remove_job(task_id)

    trigger = CronTrigger.from_crontab(cron, timezone="UTC")
    _scheduler.add_job(
        _run_scheduled_task,
        trigger=trigger,
        id=task_id,
        args=[task_id],
        replace_existing=True,
        misfire_grace_time=3600,
    )
    log.info("Scheduler: added job %s (%s)", task_id, cron)


def remove_job(task_id: str) -> None:
    """Remove a scheduled job by task_id."""
    if _scheduler is None:
        return
    if _scheduler.get_job(task_id):
        _scheduler.remove_job(task_id)
        log.info("Scheduler: removed job %s", task_id)


def set_job_enabled(task_id: str, active: bool) -> None:
    """Pause or resume a scheduled job."""
    if _scheduler is None:
        return
    job = _scheduler.get_job(task_id)
    if active:
        if job:
            job.resume()
        # Job may not exist yet (was paused before a restart); re-add it from DB
        else:
            import db
            db_path = db.get_db_path()
            task = db.get_scheduled_task(db_path, task_id)
            if task:
                add_job(task)
        log.info("Scheduler: enabled job %s", task_id)
    else:
        if job:
            job.pause()
        log.info("Scheduler: paused job %s", task_id)


async def _run_scheduled_task(task_id: str) -> None:
    """Internal job runner. Always updates last_run/next_run in finally block."""
    import db
    from main import _handle_create_background_task

    db_path = db.get_db_path()
    task = db.get_scheduled_task(db_path, task_id)
    if not task or not task["is_active"]:
        return
    user = db.get_user_by_id(db_path, task["user_id"])
    if not user:
        log.warning("_run_scheduled_task: user %s not found for task %s", task["user_id"], task_id)
        return

    log.info("_run_scheduled_task: firing task %s for user %s", task_id, task["user_id"])
    try:
        await _handle_create_background_task(
            request=task["task_description"],
            description=task["task_description"],
            history=_history,
            user_id=task["user_id"],
        )
    except Exception:
        log.exception("_run_scheduled_task: task %s raised unexpectedly", task_id)
    finally:
        # Always advance the schedule — a failed run must not freeze next_run
        now = datetime.now(timezone.utc).isoformat()
        next_run = compute_next_run(task["cron_expression"])
        db.update_scheduled_task(db_path, task_id, last_run=now, next_run=next_run)
        log.info("_run_scheduled_task: task %s completed, next_run=%s", task_id, next_run)
