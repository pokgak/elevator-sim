import os
import json
import random
import logging
import argparse
from collections import deque

from time import sleep

import paho.mqtt.client as mqtt


class ElevatorController:
    """ Data structure for elevator variable
    {
        0: {
            "status": "idle"/"driving up"/"driving down",
            "currentPosition": 0
            "queue": [1, 3]  # queue of which floor to go next
        },
        1: {
            "status": "idle"/"driving up"/"driving down",
            "currentPosition": 0
            "queue": [1, 3]  # queue of which floor to go next
        }
    }
    """

    elevators = dict()

    def __init__(self):
        logging.info("Init ElevatorController")

    def on_message(self, mqttc, obj, msg):
        logging.info(
            "No handler specified for topic {}: '{}'".format(msg.topic, msg.payload)
        )

    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected to MQTT broker. Subscribing to topics")

        # (topic, handler)
        topics = [
            ("elevator/+/status", self.elevator_status_cb),
            ("elevator/+/floorSelected", self.elevator_floorSelected_cb),
            ("floor/+/callButton/isPushed", self.floor_callButtonPushed_cb),
            # ("calendar/#", self.calendar_handler),
        ]

        for t in topics:
            logging.info(f"Subscribing to topic '{t[0]}' with callback {t[1]}")

            self.mqttc.subscribe(t[0])
            if t[1] != None:
                self.mqttc.message_callback_add(t[0], t[1])

    def get_elevator_id(self, msg) -> int:
        """ Gets ID from elevator message
        " expected topic in form elevator/{id}/#
        " Returns int
        """
        return int(str(msg.topic).split("/")[1])

    def get_floor_number(self, msg) -> int:
        """ Gets ID from floor message
        " expected topic in form floor/{id}/#
        " Returns int
        " uses get_elevator_id() for now to avoid redundant codes
        """
        return self.get_elevator_id(msg)

    # TODO: customize according to priority
    def get_closest_idle_elevator(self, dst: int) -> int:
        """ Get idle elevator from elevators list
            Try to get the closest one if possible
            returns None if there is no idle elevator currently
        """
        idle_elevators = [
            (eid, val["currentPosition"])
            for eid, val in self.elevators.items()
            if val["status"] == "idle"
        ]

        closest_id = None  # set to any high distance
        if len(idle_elevators) == 0:
            # no idle elevator
            return None

        distance_closest = 999
        for e in idle_elevators:
            # abs(current - destination)
            distance = abs(e[1] - dst)
            if distance < distance_closest:
                closest_id = e[0]
        return closest_id

    def get_closest_elevator(self, dst: int, direction: str) -> int:
        """ Get the closest elevator from elevators list
            that is moving in the same direction as var direction
        """
        # TODO: implement
        return 0

    def calendar_handler(self, mqttc, obj, msg):
        logging.info(
            "Received message for topic {}: '{}'".format(msg.topic, msg.payload)
        )

    def elevator_status_cb(self, mqttc, obj, msg):
        logging.info(
            "Received message for topic {}: '{}'".format(msg.topic, msg.payload)
        )

        data = json.loads(msg.payload)
        elevator_id = self.get_elevator_id(msg)

        # create "status" and "currentPosition" if not exists
        if elevator_id not in self.elevators:
            self.elevators[elevator_id] = {"id": elevator_id}
        elevator = self.elevators[elevator_id]

        elevator["status"] = data["status"]
        elevator["currentPosition"] = data["currentPosition"]

    def elevator_floorSelected_cb(self, mqttc, obj, msg):
        logging.info(
            "Received message for topic {}: '{}'".format(msg.topic, msg.payload)
        )

        data = json.loads(msg.payload)
        elevator_id = self.get_elevator_id(msg)

        # check if key exists, create new if not
        if elevator_id not in self.elevators:
            self.elevators[elevator_id] = {}
        elevator = self.elevators[elevator_id]

        if "queue" not in elevator:
            elevator["queue"] = deque()

        for f in data["selectedFloors"]:
            # TODO: sort selectedFloors array?
            # only add to queue if not selected already
            if f not in elevator["queue"]:
                elevator["queue"].append(f)

        next_dst = elevator["queue"].popleft()
        topic = f"elevator/{elevator_id}/nextDestination"
        self.mqttc.publish(topic, next_dst)
        logging.info(f"Published to topic: '{topic}'; payload: {next_dst}")

    def floor_callButtonPushed_cb(self, mqttc, obj, msg):
        logging.info(
            "Received message for topic {}: '{}'".format(msg.topic, msg.payload)
        )

        """
        1. get idle elevator
            1.1 if no idle available, get closest elevator with same direction (up/down)
        2. send elevator to floor
            - topic 'elevator/{id}/nextDestination
            - payload: {nextDestination}
        """

        source = self.get_floor_number(msg)
        direction = str(msg.payload)

        elevator_id = self.get_closest_idle_elevator(source)
        if elevator_id is None:
            elevator_id = self.get_closest_elevator(source, direction)

        topic = f"elevator/{elevator_id}/nextDestination"
        payload = str(source)
        self.mqttc.publish(topic, payload)
        logging.info(f"published to topic: '{topic}'; payload: '{payload}'")

    def start(self, host, port):
        self.mqttc = mqtt.Client()
        self.mqttc.connect(host, int(port))
        self.mqttc.on_message = self.on_message
        self.mqttc.on_connect = self.on_connect

        self.mqttc.loop_forever()


class Simulator:
    def __init__(self, loglevel):
        random.seed()

        if not isinstance(loglevel, int):
            raise ValueError("Invalid log level: {}".format(loglevel))
        logging.basicConfig(level=loglevel)

        self.controller = ElevatorController()

    def start(self, host="localhost", port=1883):
        logging.info("Starting simulation")

        self.controller.start(host, port)


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
        "-log",
        action="store",
        dest="log",
        default="WARNING",
        help="default: WARNING\nAvailable: INFO DEBUG WARNING ERROR CRITICAL",
    )

    args = argp.parse_args()

    host = os.getenv("mqtt_host", args.host)
    port = os.getenv("mqtt_port", args.port)
    loglevel = os.getenv("log_level", args.log)

    simulator = Simulator(getattr(logging, loglevel.upper()))
    simulator.start(host=host, port=port)
