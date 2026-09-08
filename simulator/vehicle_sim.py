import random
import math
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from simulator.config import VehicleConfig, INTERVAL_SECONDS
from simulator.routes import ROUTES
from simulator.schedules import get_route_schedule


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class VehicleSimulator:
    def __init__(self, config: VehicleConfig):
        self.config = config
        raw_route = ROUTES[config.route_index]
        self.route, self.stops, self.target_speeds = self.densify_route(raw_route, max_segment_km=0.05)
        
        self.segment_distances = []
        for i in range(len(self.route)-1):
            self.segment_distances.append(haversine_km(self.route[i][0], self.route[i][1], self.route[i+1][0], self.route[i+1][1]))
        if not self.segment_distances:
            self.segment_distances.append(0.0)
            
        self.current_segment_index = 0
        self.distance_along_segment_km = 0.0
        
        self.soc = random.uniform(55, 92)
        self.speed = 0.0
        self.heading = 0.0
        self.charging = False
        self.battery_temp = random.uniform(25, 32)
        self.seq = 0
        self.direction = 1  # 1 = forward, -1 = reverse along route
        self.stop_timer = 0
        self.current_position = self.route[0] if self.route else (0.0, 0.0)
        
        # Position bus according to current real-world schedule timing
        self.sync_to_schedule()

    def sync_to_schedule(self, simulation_time: datetime | None = None):
        """Place the bus deterministically on its road shape for the service clock.

        The position is derived from time, vehicle departure offset and route
        distance. It never integrates a random heading or a straight-line hop.
        """
        total_route_km = sum(self.segment_distances)
        if total_route_km <= 0 or len(self.route) < 2:
            return

        service_time = simulation_time or datetime.now(ZoneInfo("Asia/Kolkata"))
        if service_time.tzinfo is None:
            service_time = service_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        else:
            service_time = service_time.astimezone(ZoneInfo("Asia/Kolkata"))

        seconds_now = service_time.hour * 3600 + service_time.minute * 60 + service_time.second
        schedule = get_route_schedule(self.config.route_index, self.config.vehicle_code)
        if schedule:
            service_start = schedule["service_start_minute"] * 60
            service_end = schedule["service_end_minute"] * 60
            departure_offset = schedule["departure_offset_minutes"] * 60
            one_way_seconds = schedule["one_way_runtime_minutes"] * 60
            terminal_dwell_seconds = schedule["terminal_layover_minutes"] * 60
        else:
            # Legacy non-Bikaner simulator vehicles retain a deterministic fallback.
            service_start = 6 * 3600
            service_end = 22 * 3600 + 30 * 60
            departure_offset = 0
            cruise_speed_kph = 26.0
            one_way_seconds = max(15 * 60, (total_route_km / cruise_speed_kph) * 3600)
            terminal_dwell_seconds = 4 * 60

        if seconds_now < service_start + departure_offset or seconds_now > service_end:
            self.direction = 1
            self.speed = 0.0
            self.current_segment_index = 0
            self.distance_along_segment_km = 0.0
            self.current_position = self.route[0]
            self._update_heading()
            return

        cruise_speed_kph = total_route_km / (one_way_seconds / 3600)
        round_trip_seconds = 2 * (one_way_seconds + terminal_dwell_seconds)
        phase = (seconds_now - service_start - departure_offset) % round_trip_seconds

        if phase < one_way_seconds:
            self.direction = 1
            progress_frac = phase / one_way_seconds
            self.speed = cruise_speed_kph
        elif phase < one_way_seconds + terminal_dwell_seconds:
            self.direction = -1
            progress_frac = 1.0
            self.speed = 0.0
        elif phase < (2 * one_way_seconds) + terminal_dwell_seconds:
            self.direction = -1
            progress_frac = 1.0 - ((phase - one_way_seconds - terminal_dwell_seconds) / one_way_seconds)
            self.speed = cruise_speed_kph
        else:
            self.direction = 1
            progress_frac = 0.0
            self.speed = 0.0

        target_km = max(0.0, min(total_route_km, progress_frac * total_route_km))

        accumulated = 0.0
        for idx, seg_km in enumerate(self.segment_distances):
            if accumulated + seg_km >= target_km:
                self.current_segment_index = idx
                self.distance_along_segment_km = max(0.0, target_km - accumulated)
                frac = 0.0 if seg_km <= 0 else self.distance_along_segment_km / seg_km
                p1, p2 = self.route[idx], self.route[idx + 1]
                self.current_position = (
                    p1[0] + (p2[0] - p1[0]) * frac,
                    p1[1] + (p2[1] - p1[1]) * frac,
                )
                break
            accumulated += seg_km
        else:
            self.current_segment_index = max(0, len(self.route) - 2)
            self.distance_along_segment_km = self.segment_distances[-1]
            self.current_position = self.route[-1]
        self._update_heading()
        
    @staticmethod
    def densify_route(waypoints, max_segment_km=0.05):
        if len(waypoints) < 2:
            return waypoints, [False]*len(waypoints), [25]*len(waypoints)
            
        new_route = [waypoints[0]]
        is_original = [True]
        target_speeds = []
        
        for i in range(len(waypoints) - 1):
            p1 = waypoints[i]
            p2 = waypoints[i+1]
            dist = haversine_km(p1[0], p1[1], p2[0], p2[1])
            
            speed = random.uniform(40, 60) if dist > 0.5 else random.uniform(15, 35)
            
            if dist > max_segment_km:
                num_segments = math.ceil(dist / max_segment_km)
                for j in range(1, num_segments):
                    frac = j / num_segments
                    lat = p1[0] + (p2[0] - p1[0]) * frac
                    lng = p1[1] + (p2[1] - p1[1]) * frac
                    new_route.append((lat, lng))
                    is_original.append(False)
                    target_speeds.append(speed)
            
            new_route.append(p2)
            is_original.append(True)
            target_speeds.append(speed)
            
        target_speeds.append(target_speeds[-1] if target_speeds else 0)
        
        original_count = 0
        stops = [False] * len(new_route)
        for i, orig in enumerate(is_original):
            if orig:
                original_count += 1
                if original_count % 5 == 0:
                    stops[i] = True
                    
        return new_route, stops, target_speeds

    def tick(self, simulation_time: datetime | None = None) -> dict:
        """Generate one telemetry payload."""
        self.seq += 1
        self.sync_to_schedule(simulation_time)
        self._update_battery()

        lat, lng = self._get_current_pos()
        
        return {
            "device_id": self.config.device_code,
            "vehicle_id": self.config.vehicle_code,
            "event_id": str(uuid.uuid4()),
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "location": {
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "accuracy_m": round(random.uniform(3, 15), 1),
            },
            "motion": {
                "speed_kph": round(self.speed, 1),
                "heading_deg": round(self.heading, 1),
            },
            "energy": {
                "soc_pct": round(self.soc, 1),
                "estimated_range_km": round(self.soc * 2.5, 1),
                "charging": self.charging,
            },
            "diagnostics": {
                "dtcs": [],
                "battery_temp_c": round(self.battery_temp, 1),
            },
            "connectivity": {
                "network": "4G",
                "firmware": "0.3.1",
            },
            "seq": self.seq,
        }
    
    def _move(self, distance_km):
        if len(self.route) < 2:
            return
            
        remaining_dist = distance_km
        while remaining_dist > 0:
            seg_dist = self.segment_distances[self.current_segment_index]
            dist_to_end = seg_dist - self.distance_along_segment_km
            
            if remaining_dist < dist_to_end:
                self.distance_along_segment_km += remaining_dist
                remaining_dist = 0
            else:
                remaining_dist -= dist_to_end
                self.current_segment_index += self.direction
                self.distance_along_segment_km = 0.0
                
                if self.current_segment_index >= len(self.route) - 1:
                    self.direction = -1
                    self.current_segment_index = len(self.route) - 2
                elif self.current_segment_index < 0:
                    self.direction = 1
                    self.current_segment_index = 0
                    
                if self.stops[self.current_segment_index]:
                    self.stop_timer = random.uniform(15, 30)
                    break
                    
        self._update_heading()

    def _get_current_pos(self):
        if self.current_position:
            return self.current_position
        if len(self.route) < 2:
            return self.route[0]
            
        p1 = self.route[self.current_segment_index]
        p2 = self.route[self.current_segment_index + 1] if self.direction == 1 else self.route[self.current_segment_index - 1]
        
        seg_dist = self.segment_distances[self.current_segment_index]
        if seg_dist == 0:
            return p1
            
        frac = self.distance_along_segment_km / seg_dist
        
        if self.direction == -1:
            frac = 1.0 - frac
            
        lat = p1[0] + (self.route[self.current_segment_index + 1][0] - p1[0]) * frac
        lng = p1[1] + (self.route[self.current_segment_index + 1][1] - p1[1]) * frac
        return lat, lng
        
    def _update_heading(self):
        if len(self.route) < 2:
            return
            
        idx = self.current_segment_index
        next_idx = min(idx + self.direction, len(self.route) - 1)
        next_idx = max(next_idx, 0)
        
        if idx != next_idx:
            lat1, lng1 = self.route[idx]
            lat2, lng2 = self.route[next_idx]
            new_heading = (math.degrees(math.atan2(lng2 - lng1, lat2 - lat1)) + 360) % 360
            
            # EMA for heading with 360 wraparound handling
            diff = (new_heading - self.heading + 180) % 360 - 180
            self.heading = (self.heading + diff * 0.7) % 360

    def _update_battery(self):
        if self.charging:
            self.soc = min(100, self.soc + random.uniform(1, 3))
            self.battery_temp = min(42, self.battery_temp + random.uniform(0, 0.5))
            if self.soc >= 95:
                self.charging = False
        else:
            drain = random.uniform(0.1, 0.5)
            self.soc = max(0, self.soc - drain)
            self.battery_temp = max(20, self.battery_temp - random.uniform(0, 0.2))
            if self.soc < 15:
                self.charging = True
