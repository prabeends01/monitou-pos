"""Stage 3 — CLAUDE.md Section 11.3/11.11: plan feature-gate resolution.
Uses the real seeded catalog (`app.seed_plans.seed_plans`) rather than
hand-rolled fixture rows, so these tests break if `app/plan_catalog.py`
ever drifts from the BASIC/ESSENTIAL/ENTERPRISE mapping in the spec.
"""

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.entitlement import TenantFeatureOverride
from app.models.plan import Feature, Plan
from app.models.tenant import Tenant
from app.seed_plans import seed_plans
from app.services.entitlements import can_use_feature, require_feature


@pytest.fixture
def plans(session: Session) -> dict[str, Plan]:
    seed_plans(session)
    return {p.code: p for p in session.exec(select(Plan)).all()}


def _tenant(session: Session, code: str, plan: Plan) -> Tenant:
    tenant = Tenant(tenant_code=code, company_name=code, active_plan_id=plan.id)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


def _feature(session: Session, code: str) -> Feature:
    feature = session.exec(select(Feature).where(Feature.code == code)).first()
    assert feature is not None, f"seed_plans didn't create feature {code}"
    return feature


def test_basic_tenant_lacks_essential_feature(session: Session, plans: dict[str, Plan]):
    tenant = _tenant(session, "T-BASIC", plans["BASIC"])
    assert can_use_feature(session, tenant.id, "BARCODE_GENERATION") is False


def test_essential_tenant_has_essential_feature(session: Session, plans: dict[str, Plan]):
    tenant = _tenant(session, "T-ESSENTIAL", plans["ESSENTIAL"])
    assert can_use_feature(session, tenant.id, "BARCODE_GENERATION") is True


def test_essential_tenant_lacks_enterprise_feature(session: Session, plans: dict[str, Plan]):
    tenant = _tenant(session, "T-ESSENTIAL2", plans["ESSENTIAL"])
    assert can_use_feature(session, tenant.id, "INTER_WAREHOUSE_TRANSFER") is False


def test_enterprise_tenant_has_every_feature(session: Session, plans: dict[str, Plan]):
    tenant = _tenant(session, "T-ENTERPRISE", plans["ENTERPRISE"])
    for code in ("BARCODE_GENERATION", "INTER_WAREHOUSE_TRANSFER", "PRODUCT_MASTER", "CUSTOM_REPORTS"):
        assert can_use_feature(session, tenant.id, code) is True


def test_all_plans_have_shared_basic_feature(session: Session, plans: dict[str, Plan]):
    for plan_code in ("BASIC", "ESSENTIAL", "ENTERPRISE"):
        tenant = _tenant(session, f"T-{plan_code}-BASE", plans[plan_code])
        assert can_use_feature(session, tenant.id, "PRODUCT_MASTER") is True


def test_unknown_feature_code_fails_closed(session: Session, plans: dict[str, Plan]):
    tenant = _tenant(session, "T-UNKNOWN", plans["ENTERPRISE"])
    assert can_use_feature(session, tenant.id, "NOT_A_REAL_FEATURE") is False


def test_tenant_with_no_active_plan_fails_closed(session: Session, plans: dict[str, Plan]):
    tenant = Tenant(tenant_code="T-NO-PLAN", company_name="No Plan")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    assert can_use_feature(session, tenant.id, "PRODUCT_MASTER") is False


def test_override_grants_restricted_feature(session: Session, plans: dict[str, Plan]):
    """A Basic customer who bought Barcode as a paid add-on — Section 11's
    worked example — without moving the whole tenant to Essential."""
    tenant = _tenant(session, "T-OVERRIDE-GRANT", plans["BASIC"])
    feature = _feature(session, "BARCODE_GENERATION")
    assert can_use_feature(session, tenant.id, "BARCODE_GENERATION") is False

    session.add(
        TenantFeatureOverride(
            tenant_id=tenant.id,
            feature_id=feature.id,
            enabled=True,
            reason="purchased barcode add-on",
            approved_by=tenant.id,  # any uuid for this unit test — FK isn't enforced on sqlite
        )
    )
    session.commit()

    assert can_use_feature(session, tenant.id, "BARCODE_GENERATION") is True


def test_override_revokes_plan_feature(session: Session, plans: dict[str, Plan]):
    """The reverse direction: an Enterprise tenant with a feature switched
    off for them specifically (e.g. a compliance restriction), even though
    their plan would otherwise grant it."""
    tenant = _tenant(session, "T-OVERRIDE-REVOKE", plans["ENTERPRISE"])
    feature = _feature(session, "MULTI_LEVEL_APPROVAL")
    assert can_use_feature(session, tenant.id, "MULTI_LEVEL_APPROVAL") is True

    session.add(
        TenantFeatureOverride(
            tenant_id=tenant.id,
            feature_id=feature.id,
            enabled=False,
            reason="disabled per customer request",
            approved_by=tenant.id,
        )
    )
    session.commit()

    assert can_use_feature(session, tenant.id, "MULTI_LEVEL_APPROVAL") is False


def test_require_feature_dependency_passes_for_enabled_feature(session: Session, plans: dict[str, Plan]):
    tenant = _tenant(session, "T-DEP-OK", plans["ENTERPRISE"])
    user = _fake_user(tenant.id)
    dependency = require_feature("PRODUCT_MASTER")
    assert dependency(session=session, user=user) is None  # does not raise


def test_require_feature_dependency_raises_structured_403(session: Session, plans: dict[str, Plan]):
    tenant = _tenant(session, "T-DEP-403", plans["BASIC"])
    user = _fake_user(tenant.id)
    dependency = require_feature("BARCODE_GENERATION")

    with pytest.raises(HTTPException) as exc_info:
        dependency(session=session, user=user)

    exc = exc_info.value
    assert exc.status_code == 403
    assert exc.detail["code"] == "FEATURE_NOT_AVAILABLE"
    assert exc.detail["feature"] == "BARCODE_GENERATION"
    assert exc.detail["required_plan"] == "ESSENTIAL"
    assert exc.detail["message"] == "Barcode Generation is available in Essential and Enterprise plans."


def test_require_feature_message_for_enterprise_only_feature(session: Session, plans: dict[str, Plan]):
    tenant = _tenant(session, "T-DEP-ENT-ONLY", plans["ESSENTIAL"])
    user = _fake_user(tenant.id)
    dependency = require_feature("INTER_WAREHOUSE_TRANSFER")

    with pytest.raises(HTTPException) as exc_info:
        dependency(session=session, user=user)

    detail = exc_info.value.detail
    assert detail["required_plan"] == "ENTERPRISE"
    assert detail["message"] == "Inter-Warehouse Transfer is available in the Enterprise plan."


def _fake_user(tenant_id):
    """A bare `User`-shaped object — `require_feature`'s dependency only
    reads `.tenant_id`, and building a real authenticated user here would
    just be JWT-flow noise unrelated to what this test is checking."""

    class _U:
        pass

    u = _U()
    u.tenant_id = tenant_id
    return u
