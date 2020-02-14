# async_mqtt.py

import time
import json
import paho.mqtt.client as mqtt

from dashboard import DashboardUI, ELEVATOR_COUNT
from components import ElevatorUI, FloorUI, FLOOR_COUNT


class MQTTclient:

    client: mqtt.Client

    def __init__(self, dashboard: DashboardUI, host: str = "localhost"):
        self.host = host
        self.dashboard = dashboard
        self.client_id = "dashboard"
        self.do_run = True

        self.client = mqtt.Client(client_id=self.client_id)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # (topic, callback)
        self.callbacks = [
            ("floor/+/waiting_count", self.on_floor_waiting_count),
            ("elevator/+/actual_floor", self.on_elevator_actual_floor),
            ("elevator/+/capacity", self.on_elevator_capacity),
            ("simulation/elevator/+/queue", self.on_elevator_queue),
            ("simulation/floor/+/passenger_arrived", self.on_passenger_arrived),
            ("simulation/floor/+/arrived_count", self.on_arrived_count),
            ("simulation/passengers/expected", self.on_expected_passengers),
        ]

        for c in self.callbacks:
            self.client.message_callback_add(c[0], c[1])

    def run(self):
        self.client.loop_start()
        self.client.connect(self.host, 1883)
        while self.do_run:
            time.sleep(1)

    def on_connect(self, client, userdata, flags, rc):
        client.subscribe([(c[0], 1) for c in self.callbacks])

    def on_expected_passengers(self, client, userdata, msg):
        expected = json.loads(msg.payload)
        for floor in expected.keys():
            floor = int(floor)
            current = self.dashboard.passenger_count[floor]["expected"]
            self.dashboard.set_passenger_count_entry(
                floor, expected=current + expected[str(floor)],
            )

    def on_arrived_count(self, client, userdata, msg):
        floor = int(msg.topic.split("/")[2])
        if floor >= FLOOR_COUNT:
            # ignore error and exit
            return

        count = json.loads(msg.payload)
        assert isinstance(count, int)

        self.dashboard.set_passenger_count_entry(floor, arrived=count)

    def on_floor_waiting_count(self, client, userdata, msg):
        floor = int(msg.topic.split("/")[1])
        if floor >= FLOOR_COUNT:
            # ignore error and exit
            return

        count = json.loads(msg.payload)
        assert isinstance(count, int)

        floor: FloorUI = self.dashboard.get_floor(floor)
        floor.set_waiting_count(count)

    def on_elevator_actual_floor(self, client, userdata, msg):
        id = int(msg.topic.split("/")[1])
        if id >= ELEVATOR_COUNT:
            # ignore error and exit
            return

        floor = json.loads(msg.payload)
        assert isinstance(floor, int)

        elevator: ElevatorUI = self.dashboard.get_elevator(id)
        elevator.set_floor(floor)

    def on_elevator_capacity(self, client, userdata, msg):
        id = int(msg.topic.split("/")[1])
        if id >= ELEVATOR_COUNT:
            # ignore error and exit
            return

        capacity = json.loads(msg.payload)
        assert isinstance(capacity, dict)

        elevator: ElevatorUI = self.dashboard.get_elevator(id)
        elevator.set_capacity(capacity["actual"])

    def on_elevator_queue(self, client, userdata, msg):
        id = int(msg.topic.split("/")[2])
        if id >= ELEVATOR_COUNT:
            # ignore error and exit
            return

        queue_list: str = str([dst for dst in json.loads(msg.payload)])
        self.dashboard.set_queue(id, queue_list)

    def on_passenger_arrived(self, client, userdata, msg):
        # TODO
        pass

    def on_message(self, client, userdata, msg):
        pass
