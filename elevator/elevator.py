#!/usr/bin/env python3

import argparse
import logging
import os
import time
import json
from time import sleep

import paho.mqtt.client as mqtt

IDLE = "idle"
DRIVING_UP = "driving up"
DRIVING_DOWN = "driving down"

DEFAULT_WAIT_TIME = 1
MAX_CAPACITY = 10


class Elevator:
    def __init__(self, id: int, waittime=DEFAULT_WAIT_TIME, startfloor: int = 0):
        logging.info("ELEVATOR INIT")

        self.id = id
        self.floor = startfloor
        self.waitTime = waittime
        self.max_capacity = MAX_CAPACITY
        self.capacity = 0
        self.state = IDLE
        # passenger in form {"start": {startFloor}, "destination": {destFloor}}
        self.passengers = []

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
            (f"elevator/{self.id}/nextDestination", self.next_dest_cb),
            (f"elevator/{self.id}/passengerEnter", self.passenger_enter_cb),
        ]

        # subscribe to multiple topics in single SUBSCRIBE command
        # use QOS=1
        self.mqttc.subscribe([(t[0], 1) for t in topics])
        # register the callback for each topic
        for t in topics:
            self.mqttc.message_callback_add(t[0], t[1])

        self.update_status()

    def next_dest_cb(self, client, userdata, message):
        logging.info(
            f"received message: topic: {message.topic}; message: {str(message.payload)}"
        )

        destination = int(message.payload)
        if self.floor < destination:
            self.update_status(state=DRIVING_UP)
        elif self.floor > destination:
            self.update_status(state=DRIVING_DOWN)
        else:
            # do nothing
            pass

        self.moveTo(destination)

        # arrived, update current position and state
        exit_list = self.get_passenger_exiting(destination)
        self.update_status(state=IDLE, position=destination, exit_list=exit_list)

    def passenger_enter_cb(self, client, userdata, message):
        logging.info(
            f"received message: topic: {message.topic}; message: {str(message.payload)}"
        )

        """
        {
            "floor": $floor,
            "enter_list": [],
        }
        """

        payload = json.loads(message.payload)
        assert (payload["floor"] == self.floor)
        # , f"Elevator id {self.id} not on same floor {payload["floor"]} while passenger entering"

        enter_list = payload["enter_list"]

        if len(enter_list) == 0:
            # no new passengers boarded the elevator, do nothing
            return

        selected_floors = []
        for p in enter_list:
            dst = p["destination"]
            if dst not in selected_floors:
                selected_floors.append(dst)

        self.passengers += enter_list
        self.capacity += len(enter_list)
        logging.info(f"New passenger list: {self.passengers}")

        topic = f"elevator/{self.id}/floorSelected"
        new_payload = json.dumps(selected_floors)
        logging.info(
            f"sending selected floors '{new_payload}' to controller on topic '{topic}''"
        )
        self.mqttc.publish(topic, new_payload)

    def on_message(self, client, userdata, message):
        logging.info(
            f"received message: topic: {message.topic}; message: {str(message.payload)}"
        )

        logging.info(f"[{self.id}] unknown topic '{message.topic}' ignored")

    def get_passenger_exiting(self, floor: int):
        return [p for p in self.passengers if p["destination"] == floor]

    def moveTo(self, destination):
        logging.info("moveto " + str(destination))
        sleep(abs(self.floor - destination) * self.waitTime)

    def update_status(self, state: str = None, position: int = None, exit_list=None):
        """
        Publish status update

        Optionally accepts arguments to also update the current value.
        If no arguments are given, publish old value from `self`

        :param state: new state of the elevator
        :param position: new position of the elevator
        :param exit_list:
        :param enter_list:

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

        topic = f"elevator/{self.id}/status"

        payload = {}
        if state is not None:
            self.state = state
        payload["state"] = self.state

        if position is not None:
            self.floor = position
        payload["current_position"] = self.floor

        if exit_list is not None:
            capacity_after_exit = self.capacity - len(exit_list)
            payload["current_capacity"] = capacity_after_exit
            payload["passenger_exiting"] = True
            payload["exit_list"] = exit_list

            # update local state
            self.passengers = [p for p in self.passengers if p in exit_list]
            self.capacity = capacity_after_exit
            assert (
                self.capacity >= 0
            ), f"Elevator id {self.id} capacity less than 0: {self.capacity}"
        else:
            payload["passenger_exiting"] = False

        payload = json.dumps(payload)
        logging.info(f"updating status to '{payload}' on topic '{topic}''")
        self.mqttc.publish(topic, payload)

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
        default="INFO",
        help="default: WARNING\nAvailable: INFO DEBUG WARNING ERROR CRITICAL",
    )
    argp.add_argument(
        "-start", action="store", dest="start", default=0, help="default: 0",
    )

    args = argp.parse_args()

    host = os.getenv("mqtt_host", args.host)
    port = os.getenv("mqtt_port", args.port)
    eid = os.getenv("elevator_id", args.elevatorid)
    loglevel = os.getenv("log_level", args.log)
    start_floor = os.getenv("start_floor", args.start)

    logging.basicConfig(level=getattr(logging, loglevel.upper()))

    elevator = Elevator(id=int(eid), startfloor=int(start_floor))
    elevator.mqtt_init(hostname=host, port=int(port))
    elevator.run()
