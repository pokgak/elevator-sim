# data.py

from datetime import datetime


class Passenger():
    def __init__(self, start_floor: int, end_floor: int):
        self.start_floor: int = start_floor
        self.end_floor: int = end_floor

        self.start_timestamp: datetime = datetime.now()
        self.end_timestamp: datetime = None

        self.enter_elevator_timestamp: datetime = None
        self.leave_elevator_timestamp: datetime = None

    def to_json(self):
        result = {
            "start_floor": self.start_floor,
            "end_floor": self.end_floor,
            "start_timestamp": str(self.start_timestamp),
        }
        if self.end_timestamp is not None:
            result["end_timestamp"] = str(self.end_timestamp)
        if self.enter_elevator_timestamp is not None:
            result["enter_elevator_timestamp"] = str(self.enter_elevator_timestamp)
        if self.leave_elevator_timestamp is not None:
            result["leave_elevator_timestamp"] = str(self.leave_elevator_timestamp)
        return result

    def log_end(self):
        self.end_timestamp = datetime.now()

    def log_enter_elevator(self):
        self.enter_elevator_timestamp = datetime.now()

    def log_leave_elevator(self):
        self.leave_elevator_timestamp = datetime.now()
