import asyncio
import os
import httpx
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from shared.database import async_session_maker
from shared.models import Credential, QuotaSnapshot, Provider, ProviderModel
from shared.security import decrypt_secret
from router.quota import get_redis
from router.adapters import get_adapter
from shared.events import log_event_isolated

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("quota-poller")


async def poll_quotas():
    """APScheduler Job: Poll all enabled credentials and update DB + Redis."""
    logger.info("Polling quotas...")
    async with async_session_maker() as session:
        stmt = (
            select(Credential)
            .where(Credential.enabled == True)
            .options(
                selectinload(Credential.provider).selectinload(Provider.models)
            )
        )
        result = await session.execute(stmt)
        credentials = result.scalars().all()

        for cred in credentials:
            provider_name = cred.provider.name if cred.provider else "unknown"
            try:
                api_key = decrypt_secret(cred.secret_enc, cred.iv)
                adapter = get_adapter(provider_name)
                quota_info = await adapter.get_quota(cred)
                tokens = quota_info.tokens_remaining
                requests = quota_info.requests_remaining
            except Exception as exc:
                logger.error(f"Quota fetch failed for {cred.label} ({provider_name}): {exc}")
                await log_event_isolated(
                    level="WARNING",
                    component="quota",
                    event_type="quota_fetch_error",
                    message=f"Quota fetch failed for {cred.label} ({provider_name})",
                    details={"error": str(exc), "credential_id": str(cred.id)}
                )
                tokens, requests = 10000, None

            # 1. Persist snapshot
            snapshot = QuotaSnapshot(
                credential_id=cred.id,
                tokens_remaining=tokens,
                requests_remaining=requests,
            )
            session.add(snapshot)

            # 2. Update Redis per-model keys so the router can read them
            try:
                r = get_redis()
                if tokens is not None and cred.provider and cred.provider.models:
                    for model in cred.provider.models:
                        if model.enabled:
                            await r.setex(
                                f"quota:{cred.id}:{model.model_id}",
                                600,
                                tokens,
                            )
                elif tokens is not None:
                    # Fallback: no models in DB yet; write a generic key
                    await r.setex(f"quota:{cred.id}:default", 600, tokens)
            except Exception as e:
                logger.error(f"[Quota Error] Failed to write quota to Redis for {cred.label}: {e}")

        await session.commit()
    logger.info("Quota polling complete.")


async def sync_models_job():
    """APScheduler Job: Sync models from each enabled provider every 6 hours."""
    logger.info("Starting scheduled model sync...")
    async with async_session_maker() as session:
        prov_result = await session.execute(
            select(Provider)
            .where(Provider.enabled == True)
            .options(selectinload(Provider.credentials))
        )
        providers = prov_result.scalars().all()

    for provider in providers:
        # Pick the first enabled credential to use for the sync
        cred = next((c for c in provider.credentials if c.enabled), None)
        if not cred:
            logger.debug(f"No enabled credentials for {provider.name}, skipping model sync.")
            continue

        try:
            adapter = get_adapter(provider.name)
            model_infos = await adapter.list_models(cred)
        except Exception as exc:
            logger.error(f"Model list failed for {provider.name}: {exc}")
            continue

        if not model_infos:
            logger.debug(f"No models returned for {provider.name}.")
            continue

        async with async_session_maker() as session:
            # Fetch existing model_ids for this provider
            existing_stmt = select(ProviderModel.model_id).where(
                ProviderModel.provider_id == provider.id
            )
            existing_res = await session.execute(existing_stmt)
            existing_ids = {row[0] for row in existing_res.fetchall()}

            inserted = 0
            for info in model_infos:
                if info.model_id in existing_ids:
                    continue  # already known
                model_db = ProviderModel(
                    provider_id=provider.id,
                    model_id=info.model_id,
                    display_name=info.display_name,
                    context_window=info.context_window,
                    input_cost_per_1k=info.input_cost_per_1k,
                    output_cost_per_1k=info.output_cost_per_1k,
                    tier="",  # unassigned until admin sets it
                    supports_streaming=info.supports_streaming,
                    supports_functions=info.supports_functions,
                    enabled=False,  # disabled until admin enables
                )
                session.add(model_db)
                inserted += 1

            await session.commit()
            if inserted:
                logger.info(f"Synced {inserted} new models for {provider.name}.")


async def collect_usage_job():
    """APScheduler Job: Prune request logs older than 90 days to keep table lean."""
    from sqlalchemy import delete as sa_delete
    from datetime import datetime, timezone, timedelta
    logger.info("Running usage pruning job...")
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    async with async_session_maker() as session:
        from shared.models import RequestLog
        stmt = sa_delete(RequestLog).where(RequestLog.created_at < cutoff)
        result = await session.execute(stmt)
        await session.commit()
        logger.info(f"Pruned {result.rowcount} old request log entries.")


async def main():
    scheduler = AsyncIOScheduler()
    poll_interval = int(os.environ.get("QUOTA_POLL_INTERVAL_SECONDS", "300"))
    scheduler.add_job(poll_quotas, "interval", seconds=poll_interval)
    scheduler.add_job(sync_models_job, "interval", hours=6)
    scheduler.add_job(collect_usage_job, "interval", hours=24)
    scheduler.start()

    # Run once on startup
    await poll_quotas()
    await sync_models_job()

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    asyncio.run(main())
