# controller.py

import os
import logging
import argparse
import threading
import json

import paho.mqtt.client as mqtt
from typing import List
from cps_common.data import Passenger, ElevatorData, FloorData


class Controller:
    def __init__(self):
        self.elevators: List[ElevatorData] = [ElevatorData(id) for id in range(0, 6)]
        self.floors: List[FloorData] = [FloorData(id) for id in range(0, 10)]

    def run(self, host: str = "localhost", port: int = 1883):
        # setup MQTT
        self.client = mqtt.Client("controller")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.connect(host, port)

        self.schedulerThread = threading.Thread(target=self.scheduler)

        self.schedulerThread.start()

        self.client.loop_forever()

    def on_connect(self, client, userdata, flags, rc):
        logging.info("connected to broker!")

        subscriptions = [
            ("elevator/+/status", self.on_elevator_status),
            ("elevator/+/actual_floor", self.on_elevator_actual_floor),
            ("elevator/+/capacity", self.on_elevator_capacity),
            ("floor/+/waiting_count", self.on_floor_waiting_count),
            ("floor/+/button_pressed/#", self.on_floor_button_pressed),
        ]

        # subscribe to multiple topics in a single SUBSCRIBE command
        # QOS=1
        self.client.subscribe([(s[0], 1) for s in subscriptions])
        # add callback for each subscription
        for s in subscriptions:
            self.client.message_callback_add(s[0], s[1])

    def on_disconnect(self, client, userdata, rc):
        logging.info("disconnected from broker")

    def on_elevator_status(self, client, userdata, msg):
        # logging.info(f"New message from {msg.topic}")

        id = int(msg.topic.split("/")[1])
        elevator = self.elevators[id]
        elevator.status = msg.payload.decode("utf-8")
        logging.debug(f"elevator {id} status {elevator.status}")

    def on_elevator_actual_floor(self, client, userdata, msg):
        # logging.info(f"New message from {msg.topic}")

        id = int(msg.topic.split("/")[1])
        elevator = self.elevators[id]
        elevator.floor = int(msg.payload)
        logging.debug(f"elevator {id} actual floor {elevator.floor}")

    def on_elevator_capacity(self, client, userdata, msg):
        # logging.info(f"New message from {msg.topic}")

        id = int(msg.topic.split("/")[1])
        capacity = json.loads(msg.payload)

        elevator = self.elevators[id]
        elevator.actual_capacity = capacity["actual"]
        elevator.max_capacity = capacity["max"]
        logging.debug(f"elevator {id} actual cap {elevator.actual_capacity}")
        logging.debug(f"elevator {id} max cap {elevator.max_capacity}")

    def on_floor_waiting_count(self, client, userdata, msg):
        # logging.info(f"New message from {msg.topic}")

        id = int(msg.topic.split("/")[1])
        floor = self.floors[id]
        floor.waiting_count = int(msg.payload)
        logging.debug(f"floor {id} waiting count {floor.waiting_count}")

    def on_floor_button_pressed(self, client, userdata, msg):
        # logging.info(f"New message from {msg.topic}")

        id = int(msg.topic.split("/")[1])
        floor = self.floors[id]
        # get last section of the topic: "up" or "down"
        direction = msg.topic.split("/")[-1]
        value = bool(msg.payload)
        logging.debug(f"floor {id} button direction: {direction}; value: {value}")

        if direction == "up":
            self.up_pressed = value
        elif direction == "down":
            self.down_pressed = value
        else:
            logging.warning("unknown button direction received")

    def scheduler(self):
        logging.debug(f"Start Scheduling Thread")
        t = threading.currentThread()
        while getattr(t, "do_run", True):
            # do something
            continue

if __name__ == "__main__":
    argp = argparse.ArgumentParser(description="Elevator Controller")

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
        default="ERROR",
        help="default: ERROR\nAvailable: INFO DEBUG WARNING ERROR CRITICAL",
    )

    args = argp.parse_args()

    host = os.getenv("mqtt_host", args.host)
    port = os.getenv("mqtt_port", args.port)
    loglevel = os.getenv("log_level", args.log)

    logging.basicConfig(level=getattr(logging, loglevel.upper()))

    logging.info("Starting controller")

    controller = Controller()
    controller.run(host=host, port=int(port))

    logging.info("Exited controller")
