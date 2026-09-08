import pytest
import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
import app.models  # Import all models to register with Base.metadata
from app.models.department import Department
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle, VehicleType
from app.models.device import Device, DeviceStatus
from app.models.city import City
from app.models.charging_center import ChargingCenter
from app.models.route import Route
from app.models.stop import Stop
from app.models.route_stop import RouteStop
from app.models.vehicle_route import VehicleRoute
from app.models.help_contact import HelpContact
from app.models.telemetry import TelemetryLatest, TelemetryEvent
from app.core.security import hash_password, create_access_token
from app.core.database import get_db
from app.main import app

# Use SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Seed Fixtures ---

@pytest.fixture
async def departments(db_session: AsyncSession):
    transport = Department(name="Transport Department", code="TRANSPORT", description="Bus fleet")
    fire = Department(name="Fire Department", code="FIRE", description="Fire EVs")
    electricity = Department(name="Electricity Department", code="ELECTRICITY", description="Utility EVs")
    db_session.add_all([transport, fire, electricity])
    await db_session.commit()
    await db_session.refresh(transport)
    await db_session.refresh(fire)
    await db_session.refresh(electricity)
    return {"transport": transport, "fire": fire, "electricity": electricity}


@pytest.fixture
async def users(db_session: AsyncSession, departments):
    admin = User(
        email="admin@test.gov",
        hashed_password=hash_password("admin123"),
        full_name="Platform Admin",
        role=UserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    transport_admin = User(
        email="transport@test.gov",
        hashed_password=hash_password("transport123"),
        full_name="Transport Admin",
        role=UserRole.DEPARTMENT_ADMIN,
        department_id=departments["transport"].id,
        is_active=True,
    )
    fire_admin = User(
        email="fire@test.gov",
        hashed_password=hash_password("fire123"),
        full_name="Fire Admin",
        role=UserRole.DEPARTMENT_ADMIN,
        department_id=departments["fire"].id,
        is_active=True,
    )
    dispatcher = User(
        email="dispatcher@test.gov",
        hashed_password=hash_password("dispatch123"),
        full_name="Bus Dispatcher",
        role=UserRole.DISPATCHER,
        department_id=departments["transport"].id,
        is_active=True,
    )
    inactive_user = User(
        email="inactive@test.gov",
        hashed_password=hash_password("inactive123"),
        full_name="Inactive User",
        role=UserRole.DEPARTMENT_ADMIN,
        department_id=departments["transport"].id,
        is_active=False,
    )
    db_session.add_all([admin, transport_admin, fire_admin, dispatcher, inactive_user])
    await db_session.commit()
    for u in [admin, transport_admin, fire_admin, dispatcher, inactive_user]:
        await db_session.refresh(u)
    return {
        "admin": admin,
        "transport_admin": transport_admin,
        "fire_admin": fire_admin,
        "dispatcher": dispatcher,
        "inactive": inactive_user,
    }


@pytest.fixture
async def vehicles(db_session: AsyncSession, departments):
    bus = Vehicle(
        vehicle_code="bus-test-001",
        vehicle_type=VehicleType.ELECTRIC_BUS,
        department_id=departments["transport"].id,
        make="Tata", model="Starbus EV", year=2024,
        is_active=True, public_visible=True,
    )
    fire_truck = Vehicle(
        vehicle_code="fire-test-001",
        vehicle_type=VehicleType.FIRE_EV,
        department_id=departments["fire"].id,
        make="Tata", model="Nexon EV", year=2025,
        is_active=True, public_visible=True,
    )
    db_session.add_all([bus, fire_truck])
    await db_session.commit()
    await db_session.refresh(bus)
    await db_session.refresh(fire_truck)
    return {"bus": bus, "fire_truck": fire_truck}


@pytest.fixture
async def devices(db_session: AsyncSession, vehicles):
    bus_device = Device(
        device_code="dev-bus-test-001",
        vehicle_id=vehicles["bus"].id,
        firmware_version="0.3.1",
        status=DeviceStatus.ACTIVE,
    )
    fire_device = Device(
        device_code="dev-fire-test-001",
        vehicle_id=vehicles["fire_truck"].id,
        firmware_version="0.3.1",
        status=DeviceStatus.ACTIVE,
    )
    db_session.add_all([bus_device, fire_device])
    await db_session.commit()
    await db_session.refresh(bus_device)
    await db_session.refresh(fire_device)
    return {"bus_device": bus_device, "fire_device": fire_device}


def make_auth_header(user: User) -> dict:
    """Generate auth header for a test user."""
    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "department_id": str(user.department_id) if user.department_id else None,
    })
    return {"Authorization": f"Bearer {token}"}
