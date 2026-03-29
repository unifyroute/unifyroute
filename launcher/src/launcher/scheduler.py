from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging

from credential_vault.main import refresh_oauth_tokens
from quota_poller.main import poll_quotas, sync_models_job, collect_usage_job
from selfheal.health_prober import probe_all_providers
from selfheal.incident_tracker import cleanup_old_incidents

logger = logging.getLogger("launcher.scheduler")

def start_scheduler() -> AsyncIOScheduler:
    """Initialize and start the unified background task scheduler."""
    scheduler = AsyncIOScheduler()
    
    # Register tasks from Credential Vault
    scheduler.add_job(refresh_oauth_tokens, "interval", minutes=10, id="refresh_oauth_tokens")
    
    # Register tasks from Quota Poller
    scheduler.add_job(poll_quotas, "interval", minutes=5, id="poll_quotas")
    scheduler.add_job(sync_models_job, "interval", hours=24, id="sync_models_job")
    scheduler.add_job(collect_usage_job, "interval", hours=1, id="collect_usage_job")

    # Self-healing: proactive health probes every 2 minutes
    scheduler.add_job(probe_all_providers, "interval", minutes=2, id="health_prober")
    # Self-healing: prune stale incident data every hour
    scheduler.add_job(cleanup_old_incidents, "interval", hours=1, id="incident_cleanup")
    
    scheduler.start()
    logger.info(f"Started unified scheduler with {len(scheduler.get_jobs())} jobs.")
    return scheduler

def shutdown_scheduler(scheduler: AsyncIOScheduler):
    """Shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Shutdown unified scheduler.")
