# elevator.py

import os
import logging
import argparse
import threading
import time

import json
import paho.mqtt.client as mqtt

from typing import List
from cps_common.data import Passenger, ElevatorData


class Floor:
    def __init__(self, id: int):
        self.floor: int = id
        self.client = mqtt.Client(f"floor{self.floor}")

        self.waiting_list: List[Passenger] = []
        self.arrived_list: List[Passenger] = []
        self.elevators: List[ElevatorData] = [ElevatorData(id) for id in range(0, 6)]

        self.waiting_count_thread = threading.Thread(target=self.update_waiting_count)

    def run(self, host: str = "localhost", port: int = 1883):
        # setup MQTT
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.connect(host, port)

        self.waiting_count_thread.start()

        self.client.loop_forever()

    def update_waiting_count(self):
        t = threading.currentThread()
        while getattr(t, "do_run", True):
            time.sleep(1)
            self.client.publish(
                f"floor/{self.floor}/waiting_count", json.dumps(len(self.waiting_list))
            )

    def on_connect(self, client, userdata, flags, rc):
        logging.info("connected to broker!")

        subscriptions = [
            (
                f"simulation/floor/{self.floor}/passenger_waiting",
                self.on_passenger_waiting,
            ),
            (
                f"simulation/floor/{self.floor}/passenger_arrived",
                self.on_passenger_arrived,
            ),
            (f"elevator/+/door", self.on_elevator_door),
            (f"elevator/+/capacity", self.on_elevator_capacity),
            (f"elevator/+/status", self.on_elevator_status),
            (f"elevator/+/actual_floor", self.on_elevator_actual_floor),
        ]

        # subscribe to multiple topics in a single SUBSCRIBE command
        # QOS=1
        self.client.subscribe([(s[0], 1) for s in subscriptions])
        # add callback for each subscription
        for s in subscriptions:
            self.client.message_callback_add(s[0], s[1])

    def on_disconnect(self, client, userdata, rc):
        logging.info("disconnected from broker")

    def on_elevator_actual_floor(self, client, userdata, msg):
        elevator_id = int(msg.topic.split("/")[1])
        self.elevators[elevator_id].floor = int(msg.payload)

    def on_elevator_capacity(self, client, userdata, msg):
        # logging.info(f"New message from {msg.topic}")

        elevator_id = int(msg.topic.split("/")[1])
        # logging.debug(f"payload: {str(msg.payload)}")
        capacity = json.loads(msg.payload)
        # logging.debug(f"capacity: {capacity}")
        # logging.debug(f"id {elevator_id}: capacity: {capacity}")

        self.elevators[elevator_id].max_capacity = capacity["max"]
        self.elevators[elevator_id].actual_capacity = capacity["actual"]

    def on_elevator_status(self, client, userdata, msg):
        # logging.info(f"New message from {msg.topic}")

        elevator_id = int(msg.topic.split("/")[1])
        status = msg.payload.decode("utf-8")

        # logging.debug(f"id {elevator_id}: status: {status}")
        self.elevators[elevator_id].status = status

    def on_elevator_door(self, client, userdata, msg):
        # logging.info(f"New message from {msg.topic}")

        status = msg.payload.decode("utf-8")
        elevator_id = int(msg.topic.split("/")[1])
        # logging.debug(
        #     f"status: {status}; elevator floor: {self.elevators[elevator_id].floor}"
        # )

        if (self.elevators[elevator_id].floor == self.floor) and (
            status == "open" and len(self.waiting_list) > 0
        ):
            enter_list: List[Passenger] = []
            free = (
                self.elevators[elevator_id].max_capacity
                - self.elevators[elevator_id].actual_capacity
            )
            while len(enter_list) < free and len(self.waiting_list) > 0:
                enter_list.append(self.waiting_list.pop())

            payload = json.dumps([p.to_json() for p in enter_list])
            self.client.publish(
                f"simulation/elevator/{elevator_id}/passenger", payload, qos=2
            )
            self.client.publish(
                f"floor/{self.floor}/waiting_count", len(self.waiting_list), qos=1
            )

        # re-push or disable call button if there is still passenger waiting
        self.push_call_button()

    def on_passenger_waiting(self, client, userdata, msg):
        # logging.info(f"New message from {msg.topic}")

        # TODO: validate schema

        # convert the payload to JSON
        try:
            waiting_list = json.loads(msg.payload)
        except json.JSONDecodeError:
            logging.error("Wrong/faulty JSON message format")
            # skip wrong message format
            return

        # convert the JSON to Passenger objects
        self.waiting_list += [
            Passenger(start_floor=p["start"], end_floor=p["destination"])
            for p in waiting_list
        ]
        logging.debug(f"waiting list count: {len(self.waiting_list)}")

        self.client.publish(
            f"floor/{self.floor}/waiting_count", len(self.waiting_list), qos=1
        )
        self.push_call_button()

    def on_passenger_arrived(self, client, userdata, msg):
        logging.info(f"New message from {msg.topic}")

        # convert the payload to JSON
        arrived_list = json.loads(msg.payload)

        # log end time
        logged_passenger: List[Passenger] = []
        for p in arrived_list:
            p: Passenger = Passenger.from_json_dict(p)
            p.log_end()
            logged_passenger.append(p)
        self.arrived_list += logged_passenger
        logging.debug(f"arrived list: {self.arrived_list}")
        self.client.publish(
            f"simulation/floor/{self.floor}/arrived_count",
            len(self.arrived_list),
            qos=1,
        )
        # publish logged passenger to record
        self.client.publish(
            f"record/floor/{self.floor}/passenger_arrived",
            json.dumps([p.to_json() for p in logged_passenger]),
            qos=2,
        )

    def push_call_button(self):
        # logging.info("pushing call button")

        up: bool = False
        down: bool = False
        for p in self.waiting_list:
            up = up or (p.end_floor > self.floor)
            down = down or (p.end_floor < self.floor)
        # logging.debug(f"button pushed: up: {up}; down: {down}")

        self.client.publish(f"floor/{self.floor}/button_pressed/up", up, qos=1)
        self.client.publish(f"floor/{self.floor}/button_pressed/down", down, qos=1)


if __name__ == "__main__":
    argp = argparse.ArgumentParser(description="Floor")

    argp.add_argument(
        "-mqtthost",
        action="store",
        dest="host",
        default="localhost",
        help="default: localhost",
    )
    argp.add_argument(
        "-mqttport", action="store", dest="port", default=1883, help="default: 1883"
    )
    argp.add_argument(
        "-log",
        action="store",
        dest="log",
        default="DEBUG",
        help="default: ERROR\nAvailable: INFO DEBUG WARNING ERROR CRITICAL",
    )
    argp.add_argument(
        "-id", action="store", default=5, dest="floor_id", help="Floor ID",
    )

    args = argp.parse_args()

    host = os.getenv("mqtt_host", args.host)
    port = os.getenv("mqtt_port", args.port)
    loglevel = os.getenv("log_level", args.log)
    id = os.getenv("floor_id", args.floor_id)

    logging.basicConfig(level=getattr(logging, loglevel.upper()))

    logging.info(f"Starting floor {id}")

    controller = Floor(id=int(id))
    controller.run(host=host, port=int(port))

    logging.info(f"Exited elevator {id}")
