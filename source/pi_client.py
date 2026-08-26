import random


class PiClient:
    """
    Dashboard-side client.

    For now this uses simulated data so the Windows dashboard can be tested
    without the RC car. Later this class can be replaced with a WebSocket or
    TCP client that talks to the Raspberry Pi.
    """

    def __init__(self):
        self.connected = False
        self.last_command = None

    def send_command(self, command):
        self.last_command = command
        return True

    def get_status(self):
        return {
            "left_m": 1.80 + random.uniform(-0.04, 0.04),
            "center_m": 2.60 + random.uniform(-0.05, 0.05),
            "right_m": 1.45 + random.uniform(-0.04, 0.04),
            "speed_kmh": 0.0,
            "car_battery_v": 7.80,
            "pi_supply_v": 5.10,
            "steering": "CENTRE",
            "throttle": "NEUTRAL",
            "object_state": "CLEAR",
            "simulation": True,
        }
