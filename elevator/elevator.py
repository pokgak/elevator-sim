#!/usr/bin/env python3

import argparse
import logging
import os
import time
from time import sleep

import paho.mqtt.client as mqtt

IDLE = "idle"
DRIVING_UP = "driving up"
DRIVING_DOWN = "driving down"

DEFAULT_WAIT_TIME = 1


class Elevator:
    def __init__(self, id: int, waittime=DEFAULT_WAIT_TIME):
        logging.info("ELEVATOR INIT")

        self.id = id
        self.floor = 0
        self.waitTime = waittime
        self.state = IDLE

        self.mqttc = mqtt.Client()
        self.mqttc.on_message = self.on_message
        self.mqttc.on_connect = self.on_connect

    def mqtt_init(self, hostname: str = "localhost", port: int = 1883):
        logging.info("Connecting to broker. Please wait...")
        self.mqttc.connect(hostname, port)

    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected to broker!")

        self.mqttc.subscribe(topic=f"elevator/{self.id}/nextPosition")

        self.update_current_position(self.floor)
        self.update_state(self.state)

    def on_message(self, client, userdata, message):
        logging.info(
            f"received message: topic: {message.topic}; message: {str(message.payload)}"
        )

        if str(message.topic) == f"elevator/{self.id}/nextPosition":
            destination = int(message.payload)
            if self.state < destination:
                self.update_state(DRIVING_UP)
            elif self.state > destination:
                self.update_state(DRIVING_DOWN)
            else:
                # do nothing
                pass

            self.moveTo(destination)

            # arrived, update current position and state
            self.update_current_position(destination)
            self.update_state(IDLE)
        else:
            logging.info(f"[{self.id}] unknown topic '{message.topic}' ignored")

    def moveTo(self, destination):
        logging.info("moveto " + str(destination))
        sleep(abs(self.floor - destination) * self.waitTime)

    def update_state(self, newstate):
        topic = f"elevator/{self.id}/state"
        logging.info(f"updating state to '{newstate}' on topic '{topic}''")

        self.state = newstate
        self.mqttc.publish(topic=topic, payload=str(self.state))

    def update_current_position(self, newfloor):
        self.floor = newfloor
        topic = f"elevator/{self.id}/currentPosition"
        logging.info(f"updating current position to '{self.floor}' on topic '{topic}'")
        self.mqttc.publish(topic=topic, payload=str(self.floor))

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
        "-id",
        action="store",
        dest="elevatorid",
        default=0,
        help="Elevator ID default: 0",
    )
    argp.add_argument(
        "-log",
        action="store",
        dest="log",
        default="WARNING",
        help="default: WARNING\nAvailable: INFO DEBUG WARNING ERROR CRITICAL",
    )

    args = argp.parse_args()

    host = os.getenv("mqtt_host", args.host)
    port = os.getenv("mqtt_port", args.port)
    eid = os.getenv("elevator_id", args.elevatorid)
    loglevel = os.getenv("log_level", args.log)

    logging.basicConfig(level=getattr(logging, loglevel.upper()))

    elevator = Elevator(id=int(eid))
    elevator.mqtt_init(hostname=host, port=int(port))
    elevator.run()
