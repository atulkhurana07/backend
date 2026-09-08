import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List
from zoneinfo import ZoneInfo

from simulator.config import VehicleConfig, VEHICLES
from simulator.vehicle_sim import VehicleSimulator
from simulator.schedules import get_route_schedule, get_transit_plan
from app.core.database import AsyncSessionLocal
from app.schemas.telemetry import TelemetryIngestPayload
from app.services.telemetry_service import process_telemetry

logger = logging.getLogger("simulation_service")
IST = ZoneInfo("Asia/Kolkata")

class FleetSimulationManager:
    def __init__(self):
        self.is_running = False
        self._task: asyncio.Task | None = None
        self._clock_anchor: datetime | None = None
        self._clock_anchor_monotonic: float | None = None
        # Prioritize Bikaner Transit Buses
        self.simulators: List[VehicleSimulator] = [
            VehicleSimulator(cfg) for cfg in VEHICLES if cfg.vehicle_code.startswith("BUS-")
        ]

    def start(self):
        if not self.is_running:
            # Re-sync every bus to its exact timetable position along the route
            for sim in self.simulators:
                sim.sync_to_schedule(self.current_time())
            self.is_running = True
            self._task = asyncio.create_task(self._simulation_loop())
            logger.info(f"[+] In-process Fleet Simulator started with {len(self.simulators)} Bikaner EV buses (synced to timetable)")

    def stop(self):
        if self.is_running:
            self.is_running = False
            if self._task:
                self._task.cancel()
                self._task = None
            logger.info("[*] Fleet Simulator stopped")

    def get_status(self) -> dict:
        current_time = self.current_time()
        plan = get_transit_plan()
        route_windows = {
            route_code: f'{route["service_start"]}–{route["service_end"]}'
            for route_code, route in plan["simulation_routes"].items()
        }
        return {
            "is_running": self.is_running,
            "active_vehicles": len(self.simulators),
            "vehicle_codes": [s.config.vehicle_code for s in self.simulators],
            "interval_seconds": 2,
            "simulation_time": current_time.isoformat(),
            "clock_mode": "demo" if self._clock_anchor else "live",
            "timezone": "Asia/Kolkata",
            "service_window": "Route-specific",
            "route_service_windows": route_windows,
            "data_status": plan["timetable_status"],
            "route_catalog_status": plan["published_routes_status"],
            "verified_on": plan["verified_on"],
        }

    def current_time(self) -> datetime:
        if self._clock_anchor is None or self._clock_anchor_monotonic is None:
            return datetime.now(IST)
        elapsed = time.monotonic() - self._clock_anchor_monotonic
        return self._clock_anchor + timedelta(seconds=elapsed)

    def set_clock(self, time_value: str) -> dict:
        try:
            parsed_time = datetime.strptime(time_value, "%H:%M").time()
        except ValueError as exc:
            raise ValueError("time must use HH:MM format") from exc
        now = datetime.now(IST)
        self._clock_anchor = datetime.combine(now.date(), parsed_time, tzinfo=IST)
        self._clock_anchor_monotonic = time.monotonic()
        self._resync_simulators()
        return self.get_status()

    def reset_clock(self) -> dict:
        self._clock_anchor = None
        self._clock_anchor_monotonic = None
        self._resync_simulators()
        return self.get_status()

    def _resync_simulators(self) -> None:
        current_time = self.current_time()
        for sim in self.simulators:
            sim.sync_to_schedule(current_time)

    async def _simulation_loop(self):
        tick = 0
        while self.is_running:
            try:
                tick += 1
                async with AsyncSessionLocal() as db:
                    for sim in self.simulators:
                        payload_dict = sim.tick(self.current_time())
                        try:
                            payload = TelemetryIngestPayload(**payload_dict)
                            await process_telemetry(db, payload)
                        except Exception as ex:
                            logger.error(f"Error ingesting simulated telemetry for {sim.config.vehicle_code}: {ex}")
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Simulation loop unexpected error: {e}")
                await asyncio.sleep(2)

simulation_manager = FleetSimulationManager()
