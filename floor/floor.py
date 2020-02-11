# elevator.py

import os
import logging
import argparse

import json
import paho.mqtt.client as mqtt

from typing import List
from cps_common.data import Passenger


class Floor:
    def __init__(self, id: int):
        self.floor: int = id
        self.client = mqtt.Client(f"floor{self.floor}")

        self.waiting_list: List[Passenger] = []

    def run(self, host: str = "localhost", port: int = 1883):
        # setup MQTT
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.connect(host, port)

        self.client.loop_forever()

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
        ]

        # subscribe to multiple topics in a single SUBSCRIBE command
        # QOS=1
        self.client.subscribe([(s[0], 1) for s in subscriptions])
        # add callback for each subscription
        for s in subscriptions:
            self.client.message_callback_add(s[0], s[1])

    def on_disconnect(self, client, userdata, rc):
        logging.info("disconnected from broker")

    def on_passenger_waiting(self, client, userdata, msg):
        logging.info(f"New message from {msg.topic}")

        # TODO: validate schema

        # convert the payload to JSON
        waiting_list = json.loads(msg.payload)
        # convert the JSON to Passenger objects
        self.waiting_list += [
            Passenger(start_floor=s["start_floor"], end_floor=s["end_floor"])
            for s in waiting_list
        ]

        self.push_call_button()

    def on_passenger_arrived(self, client, userdata, msg):
        logging.info(f"New message from {msg.topic}")

    def push_call_button(self):
        logging.info("pushing call button")

        up: bool = False
        down: bool = False
        for p in self.waiting_list:
            logging.debug(type(p.end_floor))
            logging.debug(type(p))
            logging.debug(type(up))
            logging.debug(type(self.floor))
            up = up or (p.end_floor > self.floor)
            down = down or (p.end_floor < self.floor)
        logging.debug(f"button pushed: up: {up}; down: {down}")

        if up:
            self.client.publish(f"floor/{self.floor}/button_pressed", "up")
        if down:
            self.client.publish(f"floor/{self.floor}/button_pressed", "down")


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
        default="ERROR",
        help="default: ERROR\nAvailable: INFO DEBUG WARNING ERROR CRITICAL",
    )
    argp.add_argument(
        "-id", action="store", dest="floor_id", help="Floor ID",
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
