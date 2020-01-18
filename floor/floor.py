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
    def __init__(self, level: int):
        logging.info("ELEVATOR INIT")

        self.level = level

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

        # (topic, callback)
        topics = [
            (f"elevator/+/status", self.elevator_status_cb),
            (f"simulation/config/passengerList/floor/{self.level}", self.config_passenger_list_cb),
        ]

        # subscribe to multiple topics in single SUBSCRIBE command
        # use QOS=1
        self.mqttc.subscribe([(t[0], 1) for t in topics])
        # register the callback for each topic
        for t in topics:
            self.mqttc.message_callback_add(t[0], t[1])

    def config_passenger_list_cb(self, client, userdata, message):
        logging.info(
            f"received message: topic: {message.topic}; message: {str(message.payload)}"
        )

        """
        input-feeder will send the passenger list at time defined in test samples.
        This callback should publish a pushButton call **ONCE** for each message for
        each direction.

        Format of expected JSON message:

        [
            {
                "start": int,
                "destination": int,
            }
        ]
        """

        go_up = False
        go_down = False
        passenger_list = json.loads(message.payload)
        for p in passenger_list:
            # add passenger to queue
            self.passenger_queue.append(p)

            if not go_up or not go_down:
                go_up = p["destination"] > self.level
                go_down = p["destination"] < self.level

        logging.info(f"passenger queue current status: {self.passenger_queue}")

        if go_up:
            self.mqttc.publish(f"floor/{self.level}/callButton/isPushed/up", "true")
        if go_down:
            self.mqttc.publish(f"floor/{self.level}/callButton/isPushed/down", "true")

    def elevator_status_cb(self, client, userdata, message):
        elevator = json.loads(message.payload)
        # skip if not at current floor
        # ignore driving up status
        if elevator["state"] == "driving up" or elevator["current_position"] != self.level:
            return

        logging.info(
            f"received message: topic: {message.topic}; message: {str(message.payload)}"
        )

        """
        Format of expected JSON message:

        {
            "state": $state,
            "current_position": $pos,
            "queue": [],
            "max_capacity": $max_capacity,
            "current_capacity": $capacity,
            "passenger_exiting": true | false,
            "exit_list": [],
        }
        """

        if elevator["passenger_exiting"]:
            self.arrived_passengers.extend(elevator["exit_list"])
            logging.info(f"list arrived passengers: {self.arrived_passengers}")

        # reply with passenger enter
        if len(self.passenger_queue) != 0:
            available_capacity = elevator["max_capacity"] - elevator["current_capacity"]
            using = min(len(self.passenger_queue), available_capacity)
            logging.info(f"enter_list count: {using}; popping in range {range(0, using)}")
            enter_list = [self.passenger_queue.pop() for n in range(0, using)]
        else:
            enter_list = []

        topic = f"elevator/{self.get_elevator_id(message)}/passengerEnter"
        payload = {"floor": self.level, "enter_list": enter_list}
        logging.info(f"sending passenger entering list to elevator {self.get_elevator_id(message)}; payload: {payload}")
        self.mqttc.publish(topic, json.dumps(payload))

    def on_message(self, client, userdata, message):
        logging.info(
            f"received message: topic: {message.topic}; message: {str(message.payload)}"
        )

        logging.info(f"[{self.level}] unknown topic '{message.topic}' ignored")

    def get_elevator_id(self, msg) -> int:
        """
        Gets ID from elevator message

        expected topic in form elevator/{id}/#

        :param msg: MQTT message to parse for ID
        :return elevator ID
        """
        return int(str(msg.topic).split("/")[1])

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
    floor_level = os.getenv("floor_level", args.level)
    loglevel = os.getenv("log_level", args.log)

    logging.basicConfig(level=getattr(logging, loglevel.upper()))

    floor = Floor(level=int(floor_level))
    floor.mqtt_init(hostname=host, port=int(port))
    floor.run()
