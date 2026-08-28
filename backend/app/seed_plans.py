"""Seed/sync the plans, features, plan_features and plan_limits tables from
app/plan_catalog.py. Idempotent — safe to run on every deploy (upsert by
`code`), unlike app/seed.py which is one-shot demo data. Additive only: it
never disables a feature/limit a platform admin has since customized, it
only creates rows that don't exist yet and updates plan-level defaults.

Run: uv run python -m app.seed_plans
"""

from sqlmodel import Session, select

from app.db import engine
from app.models import Feature, Plan, PlanFeature, PlanLimit
from app.plan_catalog import FEATURES, PLAN_FEATURES, PLAN_LIMITS, PLANS


def seed_plans(session: Session) -> None:
    plans_by_code: dict[str, Plan] = {}
    for code, data in PLANS.items():
        plan = session.exec(select(Plan).where(Plan.code == code)).first()
        if plan is None:
            plan = Plan(code=code, **data)
            session.add(plan)
        else:
            for key, value in data.items():
                setattr(plan, key, value)
        plans_by_code[code] = plan
    session.commit()
    for plan in plans_by_code.values():
        session.refresh(plan)

    features_by_code: dict[str, Feature] = {}
    for code, name, module in FEATURES:
        feature = session.exec(select(Feature).where(Feature.code == code)).first()
        if feature is None:
            feature = Feature(code=code, name=name, module=module)
            session.add(feature)
        features_by_code[code] = feature
    session.commit()
    for feature in features_by_code.values():
        session.refresh(feature)

    for plan_code, feature_codes in PLAN_FEATURES.items():
        plan = plans_by_code[plan_code]
        for feature_code in feature_codes:
            feature = features_by_code[feature_code]
            link = session.exec(
                select(PlanFeature).where(
                    PlanFeature.plan_id == plan.id, PlanFeature.feature_id == feature.id
                )
            ).first()
            if link is None:
                session.add(PlanFeature(plan_id=plan.id, feature_id=feature.id, enabled=True))
            elif not link.enabled:
                link.enabled = True
                session.add(link)
    session.commit()

    for limit_code, by_plan in PLAN_LIMITS.items():
        for plan_code, value in by_plan.items():
            plan = plans_by_code[plan_code]
            row = session.exec(
                select(PlanLimit).where(
                    PlanLimit.plan_id == plan.id, PlanLimit.limit_code == limit_code
                )
            ).first()
            if row is None:
                session.add(PlanLimit(plan_id=plan.id, limit_code=limit_code, limit_value=value))
            else:
                row.limit_value = value
                session.add(row)
    session.commit()

    print(
        f"seeded/synced {len(plans_by_code)} plans, {len(features_by_code)} features, "
        f"plan_features + plan_limits from app/plan_catalog.py"
    )


if __name__ == "__main__":
    with Session(engine) as _session:
        seed_plans(_session)
