#!/usr/bin/env python3

import argparse
import logging
import os
import time
import json
from time import sleep
from collections import deque

import paho.mqtt.client as mqtt

class Floor:
    def __init__(self, number: int):
        logging.info("ELEVATOR INIT")

        self.number = number

        self.passenger_queue = deque()
        self.arrived_passengers = []

        self.mqttc = mqtt.Client()
        self.mqttc.on_message = self.on_message
        self.mqttc.on_connect = self.on_connect

    def mqtt_init(self, hostname: str = "localhost", port: int = 1883):
        logging.info("Connecting to broker. Please wait...")
        self.mqttc.connect(hostname, port)

    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected to broker!")

        topic = f"elevator/+/status"
        self.mqttc.subscribe(topic)
        self.mqttc.message_callback_add(topic, self.elevator_arrived_cb)

        topic = f"elevator/+/passengerExit"
        self.mqttc.subscribe(topic)
        self.mqttc.message_callback_add(topic, self.passenger_exit_cb)

    def elevator_arrived_cb(self, client, userdata, message):
        logging.info(
            f"received message: topic: {message.topic}; message: {str(message.payload)}"
        )

        elevator = json.loads(str(msg.payload))
        if elevator['currentPosition'] != self.level:
            # skip if not at current floor
            return

    def passenger_exit_cb(self, client, userdata, message):
        logging.info(
            f"received message: topic: {message.topic}; message: {str(message.payload)}"
        )

        elevator = json.loads(str(msg.payload))
        if elevator['currentPosition'] != self.level:
            # skip if not at current floor
            return

    def on_message(self, client, userdata, message):
        logging.info(
            f"received message: topic: {message.topic}; message: {str(message.payload)}"
        )

        logging.info(f"[{self.id}] unknown topic '{message.topic}' ignored")

    def run(self):
        logging.info("starting MQTT loop")
        self.mqttc.loop_forever()


if __name__ == "__main__":
    argp = argparse.ArgumentParser(description="simulator for mqtt messages")

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
        "-level",
        action="store",
        dest="level",
        default=0,
        help="Floor level default: 0",
    )
    argp.add_argument(
        "-log",
        action="store",
        dest="log",
        default="INFO",
        help="default: WARNING\nAvailable: INFO DEBUG WARNING ERROR CRITICAL",
    )

    args = argp.parse_args()

    host = os.getenv("mqtt_host", args.host)
    port = os.getenv("mqtt_port", args.port)
    floor_number = os.getenv("floor_level", args.level)
    loglevel = os.getenv("log_level", args.log)

    logging.basicConfig(level=getattr(logging, loglevel.upper()))

    floor = Floor(number=int(floor_number))
    floor.mqtt_init(hostname=host, port=int(port))
    floor.run()
