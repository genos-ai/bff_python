"""
Scheduled Background Tasks.

Tasks that run on a schedule (cron-based).
Registered with the broker including schedule metadata that
the TaskiqScheduler reads via LabelScheduleSource.

Schedule Format:
    schedule=[{"cron": "* * * * *", "args": [...], "kwargs": {...}}]

Cron Format:
    minute hour day_of_month month day_of_week
    "0 2 * * *"     - Daily at 2:00 AM UTC
    "*/15 * * * *"  - Every 15 minutes
    "0 0 * * 0"     - Weekly on Sunday at midnight
    "0 6 1 * *"     - Monthly on 1st at 6:00 AM

Usage:
    from modules.backend.tasks.scheduled import register_scheduled_tasks
    register_scheduled_tasks()
"""

from typing import Any

from modules.backend.core.logging import get_logger
from modules.backend.core.utils import utc_now

logger = get_logger(__name__)


async def daily_cleanup(older_than_days: int = 30) -> dict[str, Any]:
    """
    Clean up expired records from various tables. Runs daily at 2:00 AM UTC.

    Args:
        older_than_days: Delete records older than this many days

    Returns:
        Cleanup statistics
    """
    logger.info("Starting daily cleanup", extra={"older_than_days": older_than_days})

    # TODO: Implement actual cleanup logic (sessions, audit logs, temp files)

    result = {
        "status": "completed",
        "older_than_days": older_than_days,
        "tables_cleaned": [],
        "completed_at": utc_now().isoformat(),
    }

    logger.info("Daily cleanup completed", extra=result)
    return result


async def hourly_health_check() -> dict[str, Any]:
    """
    Perform periodic health checks on external services. Runs every hour.

    Returns:
        Health check results
    """
    logger.info("Starting hourly health check")

    from modules.backend.api.health import check_database, check_redis

    import asyncio
    db_check, redis_check = await asyncio.gather(
        check_database(),
        check_redis(),
        return_exceptions=True,
    )

    if isinstance(db_check, Exception):
        db_check = {"status": "error", "error": str(db_check)}
    if isinstance(redis_check, Exception):
        redis_check = {"status": "error", "error": str(redis_check)}

    checks = {"database": db_check, "redis": redis_check}
    all_healthy = all(
        c.get("status") in ("healthy", "not_configured")
        for c in checks.values()
    )

    result = {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
        "checked_at": utc_now().isoformat(),
    }

    log_level = "info" if all_healthy else "warning"
    getattr(logger, log_level)("Hourly health check completed", extra=result)
    return result


async def weekly_report_generation() -> dict[str, Any]:
    """
    Generate weekly summary reports. Runs every Sunday at 6:00 AM UTC.

    Returns:
        Report generation status
    """
    logger.info("Starting weekly report generation")

    # TODO: Implement actual report generation logic

    result = {
        "status": "completed",
        "reports_generated": [],
        "generated_at": utc_now().isoformat(),
    }

    logger.info("Weekly report generation completed", extra=result)
    return result


async def metrics_aggregation(interval_minutes: int = 15) -> dict[str, Any]:
    """
    Aggregate metrics for monitoring dashboards. Runs every 15 minutes.

    Args:
        interval_minutes: Aggregation interval

    Returns:
        Aggregation status
    """
    logger.debug("Starting metrics aggregation", extra={"interval_minutes": interval_minutes})

    # TODO: Implement actual metrics aggregation logic

    result = {
        "status": "completed",
        "interval_minutes": interval_minutes,
        "metrics_aggregated": [],
        "aggregated_at": utc_now().isoformat(),
    }

    logger.debug("Metrics aggregation completed", extra=result)
    return result


SCHEDULED_TASKS = {
    "daily_cleanup": {
        "function": daily_cleanup,
        "schedule": [{"cron": "0 2 * * *", "kwargs": {"older_than_days": 30}}],
        "retry_on_error": False,
        "description": "Clean up expired records daily at 2:00 AM UTC",
    },
    "hourly_health_check": {
        "function": hourly_health_check,
        "schedule": [{"cron": "0 * * * *"}],
        "retry_on_error": False,
        "description": "Check external service health every hour",
    },
    "weekly_report_generation": {
        "function": weekly_report_generation,
        "schedule": [{"cron": "0 6 * * 0"}],
        "retry_on_error": True,
        "max_retries": 2,
        "description": "Generate weekly summary reports on Sunday",
    },
    "metrics_aggregation": {
        "function": metrics_aggregation,
        "schedule": [{"cron": "*/15 * * * *", "kwargs": {"interval_minutes": 15}}],
        "retry_on_error": False,
        "description": "Aggregate metrics every 15 minutes",
    },
}


def register_scheduled_tasks() -> dict[str, Any]:
    """
    Register scheduled task functions with the Taskiq broker.

    Wraps plain async functions with broker.task decorators
    including their schedule configuration.

    Returns:
        Dict mapping task names to registered task objects
    """
    from modules.backend.tasks.broker import get_broker

    broker = get_broker()
    registered = {}

    for task_name, config in SCHEDULED_TASKS.items():
        task_kwargs = {
            "task_name": task_name,
            "schedule": config["schedule"],
            "retry_on_error": config["retry_on_error"],
        }

        if "max_retries" in config:
            task_kwargs["max_retries"] = config["max_retries"]

        registered[task_name] = broker.task(**task_kwargs)(config["function"])

    logger.info(
        "Scheduled tasks registered",
        extra={"task_count": len(registered), "tasks": list(registered.keys())},
    )

    return registered
