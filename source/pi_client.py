import math
import random
import time


class PiClient:
    """Safe dashboard-side AI simulation client.

    This simulator never talks to vehicle hardware. It models changing sensor,
    speed, steering, throttle, battery, obstacle and return-home behaviour so
    Senton Control can be exercised on a Windows PC without the RC car.

    v1.2.12 adds a hard PHONE UPDATE LOCK state. While that lock is active the
    Pi-side control layer rejects every movement-capable command and forces a
    stopped/neutral state. Unlock requires an explicit owner-authorised action.
    """

    MOVEMENT_COMMANDS = {"arm_auto", "demo", "takeover", "return_home"}

    def __init__(self):
        self.connected = False
        self.last_command = "manual"
        self.mode = "manual"
        self.speed = 0.0
        self.car_battery = 7.80
        self.pi_supply = 5.10
        self.distance_home = 65.0
        self.started = time.monotonic()
        self.tick = 0
        self.phone_update_locked = False
        self.phone_update_lock_reason = ""

    def enter_phone_update_lock(self, reason="Senton Link update in progress"):
        """Disable driving completely while the paired phone is updating."""
        self.phone_update_locked = True
        self.phone_update_lock_reason = reason
        self.mode = "phone_update_lock"
        self.last_command = "phone_update_lock"
        self.speed = 0.0
        return True

    def authorise_driving_after_phone_update(self, owner_approved=False):
        """Release the phone-update lock only after explicit owner approval.

        Real hardware integration must also require Senton Link reconnection,
        authentication, version verification and all safety/failsafe checks.
        """
        if not owner_approved:
            return False
        self.phone_update_locked = False
        self.phone_update_lock_reason = ""
        self.mode = "manual"
        self.last_command = "manual"
        self.speed = 0.0
        return True

    def send_command(self, command):
        # Hard Pi-side enforcement: a phone update lock rejects every command
        # that could cause driving. Stop/manual remain safe and are accepted.
        if self.phone_update_locked and command in self.MOVEMENT_COMMANDS:
            self.last_command = f"rejected:{command}"
            self.mode = "phone_update_lock"
            self.speed = 0.0
            return False

        self.last_command = command
        if command in {"manual", "arm_auto", "demo", "stop", "takeover", "return_home"}:
            self.mode = command
        return True

    def _target_speed(self, center_m):
        if self.phone_update_locked:
            return 0.0
        if self.mode in {"manual", "stop", "phone_update_lock"}:
            return 0.0
        if center_m < 0.55:
            return 0.0
        if center_m < 1.0:
            return 0.7
        if self.mode == "demo":
            return 1.6
        if self.mode == "return_home":
            return 2.2
        return 3.2

    def get_status(self):
        self.tick += 1
        t = time.monotonic() - self.started

        # Moving virtual environment: obstacles drift through the three sensors.
        left = 1.9 + 0.65 * math.sin(t / 4.8) + random.uniform(-0.06, 0.06)
        center = 2.4 + 1.05 * math.sin(t / 6.2 + 1.1) + random.uniform(-0.08, 0.08)
        right = 1.8 + 0.75 * math.sin(t / 5.5 + 2.4) + random.uniform(-0.06, 0.06)

        # Periodically introduce a closer virtual obstacle for avoidance testing.
        if self.tick % 28 in range(0, 6):
            center = max(0.38, 1.15 - (self.tick % 28) * 0.12)

        left = max(0.25, left)
        center = max(0.25, center)
        right = max(0.25, right)

        target = self._target_speed(center)
        self.speed += (target - self.speed) * 0.35
        if self.phone_update_locked or self.speed < 0.03:
            self.speed = 0.0

        if self.phone_update_locked:
            steering = "LOCKED"
            throttle = "DISABLED"
        elif self.mode == "stop":
            steering = "CENTRE"
            throttle = "NEUTRAL"
        elif center < 0.75:
            steering = "RIGHT" if left < right else "LEFT"
            throttle = "BRAKE"
        elif left < 0.9:
            steering = "RIGHT"
            throttle = "LIGHT"
        elif right < 0.9:
            steering = "LEFT"
            throttle = "LIGHT"
        elif self.speed > 0:
            steering = "CENTRE"
            throttle = "FORWARD"
        else:
            steering = "CENTRE"
            throttle = "NEUTRAL"

        nearest = min(left, center, right)
        if self.phone_update_locked:
            object_state = "PHONE UPDATE LOCK — DRIVING DISABLED"
        elif nearest < 0.55:
            object_state = "STOP / AVOID"
        elif nearest < 1.0:
            object_state = "OBJECT NEAR"
        else:
            object_state = "CLEAR"

        if self.speed > 0:
            self.car_battery = max(6.8, self.car_battery - 0.0008)
        self.pi_supply = 5.08 + random.uniform(-0.025, 0.025)

        if self.mode == "return_home" and self.speed > 0 and not self.phone_update_locked:
            self.distance_home = max(0.0, self.distance_home - self.speed / 3.6)
            if self.distance_home <= 0.1:
                self.mode = "stop"
                self.speed = 0.0
                throttle = "NEUTRAL"
                object_state = "HOME REACHED"

        return {
            "left_m": left,
            "center_m": center,
            "right_m": right,
            "speed_kmh": self.speed,
            "car_battery_v": self.car_battery,
            "pi_supply_v": self.pi_supply,
            "steering": steering,
            "throttle": throttle,
            "object_state": object_state,
            "simulation": True,
            "simulation_type": "AI",
            "sim_mode": self.mode.upper(),
            "distance_home_m": self.distance_home,
            "phone_update_locked": self.phone_update_locked,
            "driving_enabled": not self.phone_update_locked,
            "phone_update_lock_reason": self.phone_update_lock_reason,
        }
