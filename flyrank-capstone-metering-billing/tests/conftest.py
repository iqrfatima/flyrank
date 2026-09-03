import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import PLANS
from app.db import Base, get_session
from app.main import app
from app.models import Plan, Tenant

TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    for name, spec in PLANS.items():
        p = Plan(
            name=name,
            api_calls_limit=spec["api_calls_limit"],
            ai_tokens_limit=spec["ai_tokens_limit"],
            price_cents=spec["price_cents"],
        )
        session.add(p)
    session.commit()
    session.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_session():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_tenants(db_session):
    free_plan = db_session.query(Plan).filter_by(name="Free").one()
    pro_plan = db_session.query(Plan).filter_by(name="Pro").one()

    free_tenant = Tenant(
        name="Test Free Tenant",
        api_key="test_free_key_12345678",
        plan_id=free_plan.id,
        status="active",
    )
    pro_tenant = Tenant(
        name="Test Pro Tenant",
        api_key="test_pro_key_12345678",
        plan_id=pro_plan.id,
        status="active",
    )
    inactive_tenant = Tenant(
        name="Test Inactive Tenant",
        api_key="test_inactive_key_12345678",
        plan_id=free_plan.id,
        status="cancelled",
    )
    db_session.add_all([free_tenant, pro_tenant, inactive_tenant])
    db_session.commit()

    return {
        "free": free_tenant,
        "pro": pro_tenant,
        "inactive": inactive_tenant,
        "free_plan": free_plan,
        "pro_plan": pro_plan,
    }
