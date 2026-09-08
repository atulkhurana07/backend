from datetime import datetime
from zoneinfo import ZoneInfo

from simulator.config import VehicleConfig
from simulator.route_shapes import get_bikaner_geojson, get_bikaner_simulator_points
from simulator.vehicle_sim import VehicleSimulator
from simulator.schedules import get_route_schedule, get_transit_plan


IST = ZoneInfo("Asia/Kolkata")


def make_bus() -> VehicleSimulator:
    return VehicleSimulator(
        VehicleConfig("BUS-101", "DEV-BUS-101", "TRANSIT_BKN", "electric_bus", 14)
    )


def test_bikaner_shapes_are_detailed_and_shared_with_simulator():
    geometry = get_bikaner_geojson("BKN-L1")
    simulator_points = get_bikaner_simulator_points("BKN-L1")

    assert geometry is not None
    assert len(geometry["coordinates"]) > 500
    assert len(simulator_points) == len(geometry["coordinates"])
    assert simulator_points[0] == (
        geometry["coordinates"][0][1],
        geometry["coordinates"][0][0],
    )


def test_same_service_time_always_produces_same_bus_position():
    bus = make_bus()
    service_time = datetime(2026, 9, 9, 9, 30, tzinfo=IST)

    bus.sync_to_schedule(service_time)
    first_position = bus._get_current_pos()
    bus.sync_to_schedule(service_time)

    assert bus._get_current_pos() == first_position
    assert 20.0 <= bus.speed <= 35.0


def test_bus_moves_with_clock_and_parks_outside_service_hours():
    bus = make_bus()
    bus.sync_to_schedule(datetime(2026, 9, 9, 9, 30, tzinfo=IST))
    morning_position = bus._get_current_pos()

    bus.sync_to_schedule(datetime(2026, 9, 9, 9, 35, tzinfo=IST))
    assert bus._get_current_pos() != morning_position

    bus.sync_to_schedule(datetime(2026, 9, 9, 2, 0, tzinfo=IST))
    assert bus.speed == 0.0
    assert bus._get_current_pos() == bus.route[0]


def test_schedule_is_source_aware_and_route_specific():
    plan = get_transit_plan()
    schedule = get_route_schedule(14, "BUS-102")

    assert plan["published_routes_status"] == "proposed"
    assert plan["timetable_status"] == "planning_scenario_not_official"
    assert len(plan["proposed_routes"]) == 25
    assert schedule is not None
    assert schedule["route_code"] == "BKN-L1"
    assert schedule["departure_offset_minutes"] == 33


def test_each_bikaner_route_has_its_own_service_window():
    line_one = get_route_schedule(14, "BUS-101")
    line_four = get_route_schedule(17, "BUS-401")

    assert line_one is not None and line_four is not None
    assert line_one["service_start"] == "06:30"
    assert line_four["service_start"] == "07:00"
