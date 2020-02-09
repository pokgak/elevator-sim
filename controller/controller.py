# controller.py

import os
import logging
import argparse

import paho.mqtt.client as mqtt


class Controller:
    def __init__(self):
        pass

    def run(self, host: str = "localhost", port: int = 1883):
        # setup MQTT
        self.client = mqtt.Client("controller")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.connect(host, port)

        self.client.loop_forever()

    def on_connect(self, client, userdata, flags, rc):
        logging.info("connected to broker!")

        subscriptions = [
            ("elevator/+/status", self.on_elevator_status),
            ("elevator/+/actual_floor", self.on_elevator_actual_floor),
            ("elevator/+/capacity", self.on_elevator_capacity),
            ("floor/+/waiting_count", self.on_floor_waiting_count),
            ("floor/+/button_pressed", self.on_floor_button_pressed),
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
        logging.info(f"New message from {msg.topic}")

    def on_elevator_actual_floor(self, client, userdata, msg):
        logging.info(f"New message from {msg.topic}")

    def on_elevator_capacity(self, client, userdata, msg):
        logging.info(f"New message from {msg.topic}")

    def on_floor_waiting_count(self, client, userdata, msg):
        logging.info(f"New message from {msg.topic}")

    def on_floor_button_pressed(self, client, userdata, msg):
        logging.info(f"New message from {msg.topic}")


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
