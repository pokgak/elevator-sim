# elevator.py

import os
import logging
import argparse

import paho.mqtt.client as mqtt


class Elevator:
    def __init__(self, id: int, start_floor: int = 0):
        self.id = id
        self.floor = start_floor

        self.client = mqtt.Client(f"elevator{self.id}")

    def run(self, host: str = "localhost", port: int = 1883):
        # setup MQTT
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.connect(host, port)

        self.client.loop_forever()

    def on_connect(self, client, userdata, flags, rc):
        logging.info("connected to broker!")

        subscriptions = [
            (f"elevator/{self.id}/next_floor", self.on_elevator_next_floor),
            (f"simulation/elevator/{self.id}/passenger", self.on_simulation_passenger),
        ]

        # subscribe to multiple topics in a single SUBSCRIBE command
        # QOS=1
        self.client.subscribe([(s[0], 1) for s in subscriptions])
        # add callback for each subscription
        for s in subscriptions:
            self.client.message_callback_add(s[0], s[1])

    def on_disconnect(self, client, userdata, rc):
        logging.info("disconnected from broker")

    def on_elevator_next_floor(self, client, userdata, msg):
        logging.info(f"New message from {msg.topic}")

    def on_simulation_passenger(self, client, userdata, msg):
        logging.info(f"New message from {msg.topic}")


if __name__ == "__main__":
    argp = argparse.ArgumentParser(description="Elevator")

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
        "-id", action="store", dest="elevatorid", help="Elevator ID",
    )
    argp.add_argument(
        "-start", action="store", dest="start", default=0, help="default: 0",
    )

    args = argp.parse_args()

    host = os.getenv("mqtt_host", args.host)
    port = os.getenv("mqtt_port", args.port)
    loglevel = os.getenv("log_level", args.log)
    id = os.getenv("elevator_id", args.elevatorid)
    start_floor = os.getenv("start_floor", args.start)

    logging.basicConfig(level=getattr(logging, loglevel.upper()))

    logging.info(f"Starting elevator {id}")

    controller = Elevator(id=int(id), start_floor=int(start_floor))
    controller.run(host=host, port=int(port))

    logging.info(f"Exited elevator {id}")
