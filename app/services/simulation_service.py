import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from simulator.config import VehicleConfig, VEHICLES
from simulator.vehicle_sim import VehicleSimulator
from app.core.database import AsyncSessionLocal
from app.schemas.telemetry import TelemetryIngestPayload
from app.services.telemetry_service import process_telemetry

logger = logging.getLogger("simulation_service")

class FleetSimulationManager:
    def __init__(self):
        self.is_running = False
        self._task: asyncio.Task | None = None
        # Prioritize Bikaner Transit Buses
        self.simulators: List[VehicleSimulator] = [
            VehicleSimulator(cfg) for cfg in VEHICLES if cfg.vehicle_code.startswith("BUS-")
        ]

    def start(self):
        if not self.is_running:
            # Re-sync every bus to its exact timetable position along the route
            for sim in self.simulators:
                sim.sync_to_schedule()
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
        return {
            "is_running": self.is_running,
            "active_vehicles": len(self.simulators),
            "vehicle_codes": [s.config.vehicle_code for s in self.simulators],
            "interval_seconds": 2
        }

    async def _simulation_loop(self):
        tick = 0
        while self.is_running:
            try:
                tick += 1
                async with AsyncSessionLocal() as db:
                    for sim in self.simulators:
                        payload_dict = sim.tick()
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
