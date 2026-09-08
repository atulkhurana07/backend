from dataclasses import dataclass, field

BACKEND_URL = "http://localhost:8000"
INGEST_ENDPOINT = f"{BACKEND_URL}/api/ingest/telemetry"
INTERVAL_SECONDS = 2  # Telemetry send interval


@dataclass
class VehicleConfig:
    vehicle_code: str
    device_code: str
    department: str  # department code
    vehicle_type: str
    route_index: int = 0  # Which predefined route to follow


# 15 vehicles across 3 departments
VEHICLES: list[VehicleConfig] = [
    # Transport / Bus Department (6 buses)
    VehicleConfig("bus-001", "dev-bus-001", "TRANSPORT", "electric_bus", 0),
    VehicleConfig("bus-002", "dev-bus-002", "TRANSPORT", "electric_bus", 1),
    VehicleConfig("bus-003", "dev-bus-003", "TRANSPORT", "electric_bus", 2),
    VehicleConfig("bus-004", "dev-bus-004", "TRANSPORT", "electric_bus", 0),
    VehicleConfig("bus-005", "dev-bus-005", "TRANSPORT", "electric_bus", 1),
    VehicleConfig("bus-006", "dev-bus-006", "TRANSPORT", "electric_bus", 2),
    # Fire Department (4 vehicles)
    VehicleConfig("fire-001", "dev-fire-001", "FIRE", "fire_ev", 3),
    VehicleConfig("fire-002", "dev-fire-002", "FIRE", "fire_ev", 4),
    VehicleConfig("fire-003", "dev-fire-003", "FIRE", "fire_ev", 3),
    VehicleConfig("fire-004", "dev-fire-004", "FIRE", "fire_ev", 4),
    # Electricity Department (5 utility vehicles)
    VehicleConfig("util-001", "dev-util-001", "ELECTRICITY", "utility_ev", 5),
    VehicleConfig("util-002", "dev-util-002", "ELECTRICITY", "utility_ev", 6),
    VehicleConfig("util-003", "dev-util-003", "ELECTRICITY", "utility_ev", 5),
    VehicleConfig("util-004", "dev-util-004", "ELECTRICITY", "utility_ev", 6),
    VehicleConfig("util-005", "dev-util-005", "ELECTRICITY", "utility_ev", 5),
    # Bikaner Municipal E-Transit Fleet (5 Electric Buses on Lines 1-4)
    VehicleConfig("BUS-101", "DEV-BUS-101", "TRANSIT_BKN", "electric_bus", 14),
    VehicleConfig("BUS-102", "DEV-BUS-102", "TRANSIT_BKN", "electric_bus", 14),
    VehicleConfig("BUS-201", "DEV-BUS-201", "TRANSIT_BKN", "electric_bus", 15),
    VehicleConfig("BUS-301", "DEV-BUS-301", "TRANSIT_BKN", "electric_bus", 16),
    VehicleConfig("BUS-401", "DEV-BUS-401", "TRANSIT_BKN", "electric_bus", 17),
]
