"""Background usage rollup — off the request path, with failure recorded on job_runs."""

from sqlalchemy.orm import Session

from app.models import CostSnapshot, JobRun, Tenant
from app.services import tenant as tenant_service
from app.services.cost import calculate_usage_cost, current_period_bounds


def run_usage_rollup(session: Session) -> dict:
    job = JobRun(job_name="usage_rollup", status="running")
    session.add(job)
    session.flush()

    try:
        start, end = current_period_bounds()
        tenants = session.query(Tenant).all()
        processed = 0
        for tenant in tenants:
            usage = tenant_service.get_usage_rollup(session, tenant.id)
            cost = calculate_usage_cost(usage["api_calls_used"], usage["token_breakdown"])
            snapshot = (
                session.query(CostSnapshot)
                .filter_by(tenant_id=tenant.id, period_start=start)
                .one_or_none()
            )
            if snapshot is None:
                snapshot = CostSnapshot(tenant_id=tenant.id, period_start=start, period_end=end)
                session.add(snapshot)
            snapshot.period_end = end
            snapshot.api_calls_used = usage["api_calls_used"]
            snapshot.ai_tokens_used = usage["ai_tokens_used"]
            snapshot.api_calls_cost_cents = cost["api_calls_cost_cents"]
            snapshot.tokens_cost_microcents = cost["tokens_cost_microcents"]
            snapshot.total_cost_cents = cost["total_cost_cents"]
            processed += 1

        job.status = "completed"
        job.extra = {"tenantsProcessed": processed}
        from datetime import datetime, timezone

        job.finished_at = datetime.now(timezone.utc)
        print(f"[job:usage_rollup] Completed — {processed} tenants")
        return {"processed": processed}
    except Exception as err:
        from datetime import datetime, timezone

        job.status = "failed"
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = str(err)
        print(f"[job:usage_rollup] FAILED: {err}")
        raise
