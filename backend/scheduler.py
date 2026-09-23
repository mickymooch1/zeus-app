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

NOTE: This module uses process-level globals. It is only safe in a
single-worker deployment. Multi-worker deployments require an external
job store (e.g. SQLAlchemyJobStore) and a dedicated scheduler worker.
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
    if _scheduler is not None:
        log.warning("init_scheduler called while scheduler already running — ignoring")
        return
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

    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger as _CronTrigger
    import zeus_ops_agent as _ops

    _scheduler.add_job(
        _ops.health_check,
        trigger=_CronTrigger(hour=9, minute=0, timezone="UTC"),
        id="__health_check__",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _ops.daily_report,
        trigger=_CronTrigger(hour=9, minute=0, timezone="UTC"),
        id="__daily_report__",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _ops.evening_checkin,
        trigger=_CronTrigger(hour=19, minute=0, timezone="UTC"),
        id="__evening_checkin__",
        replace_existing=True,
        misfire_grace_time=1800,
    )
    _scheduler.add_job(
        _ops.ph_monitor,
        trigger=IntervalTrigger(minutes=30),
        id="__ph_monitor__",
        replace_existing=True,
        misfire_grace_time=600,
    )
    _scheduler.add_job(
        _ops.discover_monitor,
        trigger=IntervalTrigger(minutes=30),
        id="__discover_monitor__",
        replace_existing=True,
        misfire_grace_time=600,
    )
    # Every 15 min, matching the 15-minute threshold _fix_stuck_songs tests for. It
    # used to run only inside the daily 09:00 health_check, so a song whose provider
    # webhook was lost stayed "generating" — holding the user's credit — for up to 24
    # hours. Apiframe v2 is webhook-only (no status endpoint to poll), so this sweep
    # is the only thing that ever ends a stuck song.
    _scheduler.add_job(
        _ops.stuck_song_sweep,
        trigger=IntervalTrigger(minutes=15),
        id="__stuck_song_sweep__",
        replace_existing=True,
        misfire_grace_time=600,
    )
    # Security monitor (2026-09-21). The flush persists the bot guard's buffered events
    # and blocks and sends the alert-overflow summary. The scan job fires DAILY but
    # run_if_due() only actually runs it every 3 days — deliberately not a 3-day
    # interval, because an in-memory interval timer resets on every deploy (which
    # happens several times a day) and would never fire.
    import bot_guard as _bot_guard
    import security_scan as _security_scan

    _scheduler.add_job(
        _bot_guard.flush,
        trigger=IntervalTrigger(seconds=30),
        id="__security_flush__",
        replace_existing=True,
        misfire_grace_time=60,
    )
    _scheduler.add_job(
        _security_scan.run_if_due,
        trigger=_CronTrigger(hour=9, minute=30, timezone="UTC"),
        id="__security_scan__",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Zeus Clips upload hardening (2026-09-23): a clip-media upload that never
    # gets attached to a published clip within 24h is deleted — see
    # clip_uploads.sweep_orphaned_uploads. Hourly is frequent enough that an
    # abandoned upload doesn't sit around for long past its 24h grace period,
    # without being so frequent it's doing real work on every tick.
    import clip_uploads as _clip_uploads

    def _clip_upload_sweep() -> None:
        import os as _os
        import pathlib as _pathlib
        import db as _db
        deleted = _clip_uploads.sweep_orphaned_uploads(
            _db.get_db_path(),
            _pathlib.Path(_os.environ.get("CLIP_STORAGE_PATH", "/data/clips")),
        )
        if deleted:
            log.info("clip upload sweep: deleted %d orphaned upload(s)", deleted)

    _scheduler.add_job(
        _clip_upload_sweep,
        trigger=IntervalTrigger(hours=1),
        id="__clip_upload_sweep__",
        replace_existing=True,
        misfire_grace_time=1800,
    )
    log.info("Scheduler: health check, daily report, evening check-in, PH monitor, "
             "Discover monitor, stuck-song sweep, security flush + scan, "
             "clip upload sweep registered")


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
            log.info("Scheduler: enabled job %s", task_id)
        else:
            import db
            db_path = db.get_db_path()
            task = db.get_scheduled_task(db_path, task_id)
            if task:
                add_job(task)
                log.info("Scheduler: enabled job %s (re-added from DB)", task_id)
            else:
                log.warning("Scheduler: set_job_enabled(%s, True) — task not found in DB", task_id)
    else:
        if job:
            job.pause()
        log.info("Scheduler: paused job %s", task_id)


async def _run_scheduled_task(task_id: str) -> None:
    """Internal job runner. Updates last_run/next_run in finally block when task runs; skips update on pre-flight guard failures (inactive task, missing user)."""
    import db
    from zeus_agent import _handle_create_background_task

    if _history is None:
        log.error("_run_scheduled_task: _history not initialised — was init_scheduler called?")
        return

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
