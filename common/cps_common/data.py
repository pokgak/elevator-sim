# data.py

import json

import logging
from datetime import datetime
from collections import deque
from typing import Deque


class ElevatorData:
    def __init__(self, id: int):
        self.id = id
        self.floor = 0
        self.door = "open"
        self.status = "online"
        self.actual_capacity = 0
        self.max_capacity = 0

        # used by controller only
        self.queue: Deque[int] = deque()


class FloorData:
    def __init__(self, id: int):
        self.id = id
        self.waiting_count = 0
        self.up_pressed = False
        self.down_pressed = False


class Passenger:
    def __init__(
        self,
        start_floor: int,
        end_floor: int,
        start_timestamp: str = None,
        end_timestamp: str = None,
        enter_elevator: str = None,
        leave_elevator: str = None,
    ):
        # Mandatory values. This must be given at initilisation
        self.start_floor: int = start_floor
        self.end_floor: int = end_floor

        # Overwrite default values if specified
        if start_timestamp is not None:
            self.start_timestamp = start_timestamp
        else:
            self.start_timestamp: str = datetime.now().isoformat()
        if end_timestamp is not None:
            self.end_timestamp = end_timestamp
        else:
            self.end_timestamp: str = None
        if enter_elevator is not None:
            self.enter_elevator_timestamp = enter_elevator
        else:
            self.enter_elevator_timestamp: str = None
        if leave_elevator is not None:
            self.leave_elevator_timestamp = leave_elevator
        else:
            self.leave_elevator_timestamp: str = None

    def __eq__(self, value):
        if not isinstance(value, Passenger):
            return NotImplemented

        return (
            self.start_floor == value.start_floor
            and self.end_floor == value.end_floor
            and self.start_timestamp == value.start_timestamp
            and self.end_timestamp == value.end_timestamp
            and self.enter_elevator_timestamp == value.enter_elevator_timestamp
            and self.leave_elevator_timestamp == value.leave_elevator_timestamp
        )

    def __repr__(self):
        return json.dumps(self.to_json())

    @staticmethod
    def from_json_dict(p: dict):
        logging.debug(f"Passenger.from_json_dict type: {type(p)}; p: {p}")
        enter_elevator = None
        leave_elevator = None
        end = None
        start = None

        if "enter_elevator_timestamp" in p.keys():
            enter_elevator = p["enter_elevator_timestamp"]
        if "leave_elevator_timestamp" in p.keys():
            leave_elevator = p["leave_elevator_timestamp"]
        if "end_timestamp" in p.keys():
            end = p["end_timestamp"]
        if "start_timestamp" in p.keys():
            start = p["start_timestamp"]
        return Passenger(
            start_floor=p["start_floor"],
            end_floor=p["end_floor"],
            start_timestamp=start,
            end_timestamp=end,
            enter_elevator=enter_elevator,
            leave_elevator=leave_elevator,
        )

    def to_json(self):
        result = {
            "start_floor": self.start_floor,
            "end_floor": self.end_floor,
        }
        if self.start_timestamp is not None:
            result["start_timestamp"] = self.start_timestamp
        if self.end_timestamp is not None:
            result["end_timestamp"] = self.end_timestamp
        if self.enter_elevator_timestamp is not None:
            result["enter_elevator_timestamp"] = self.enter_elevator_timestamp
        if self.leave_elevator_timestamp is not None:
            result["leave_elevator_timestamp"] = self.leave_elevator_timestamp
        return result

    def log_end(self):
        self.end_timestamp = datetime.now().isoformat()

    def log_enter_elevator(self):
        self.enter_elevator_timestamp = datetime.now().isoformat()

    def log_leave_elevator(self):
        self.leave_elevator_timestamp = datetime.now().isoformat()
