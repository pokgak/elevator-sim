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
            "state": "idle" | "driving up" | "driving down",
            "current_position": 0
            "queue": [1, 3]  # queue of which floor to go next
        },
        1: {
            "state": "idle" | "driving up" | "driving down",
            "current_position": 0
            "queue": [1, 3]  # queue of which floor to go next
        }
    }
    """

    elevators = dict()

    """
    floors schema

    {
        0: {
            "up_pushed": False,
            "down_pushed": False
        }
    }
    """
    floors = dict()

    def __init__(self, floor_count: int, elevator_count: int):
        logging.info("Init ElevatorController")
        self.floors = {
            level: {"up_pushed": False, "down_pushed": False}
            for level in range(0, floor_count)
        }

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
            ("floor/+/callButton/isPushed/+", self.floor_callButtonPushed_cb),
            # ("calendar/#", self.calendar_handler),
        ]

        for t in topics:
            logging.info(f"Subscribing to topic '{t[0]}' with callback {t[1]}")

            self.mqttc.subscribe(t[0])
            if t[1] != None:
                self.mqttc.message_callback_add(t[0], t[1])

    def get_elevator_id(self, msg) -> int:
        """
        Gets ID from elevator message

        expected topic in form elevator/{id}/#

        :param msg: MQTT message to parse for ID
        :return elevator ID
        """
        return int(str(msg.topic).split("/")[1])

    def get_floor_number(self, msg) -> int:
        """
        Gets ID from floor message

        expected topic in form floor/{number}/#
        uses get_elevator_id() for now to avoid redundant codes

        :param msg: MQTT message to parse for floor number
        :return floor number
        """
        return self.get_elevator_id(msg)

    # TODO: customize according to priority
    def get_closest_idle_elevator(self, dst: int) -> int:
        """
        Get idle elevator from elevators list

        Try to get the closest one if possible

        :param dst: destination to schedule
        :return ID of the closest *idle* elevator
        :return None if there is no idle elevator currently
        """

        logging.info(f"current elevators: {self.elevators.items()}")

        idle_elevators = [
            (eid, val["current_position"])
            for eid, val in self.elevators.items()
            if val["state"] == "idle"
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
        """
        Get the closest elevator from elevators list that is moving in the
        same direction as var direction

        :param dst: destination to schedule
        :param direction: direction of elevator movement (up/down)
        :return ID of the closest elevator
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

        payload = json.loads(msg.payload)
        elevator_id = self.get_elevator_id(msg)

        # create "state" and "current_position" if not exists
        if elevator_id not in self.elevators:
            self.add_elevator(elevator_id)

        self.elevators[elevator_id]["state"] = payload["state"]
        self.elevators[elevator_id]["current_position"] = payload["current_position"]
        logging.info(f"elevator list updated: {self.elevators}")

        if payload["state"] == "idle":
            # FIXME: decide which direction of call button to disable
            self.floors[int(payload["current_position"])]["up"] = False
            self.floors[int(payload["current_position"])]["down"] = False

            if len(self.elevators[elevator_id]["queue"]) > 0:
                # send next destination
                topic = f"elevator/{elevator_id}/nextDestination"
                self.mqttc.publish(topic, int(self.elevators[elevator_id]["queue"].popleft()))

    def add_elevator(self, id: int):
        self.elevators[id] = {"id": id, "queue": deque()}

    def elevator_floorSelected_cb(self, mqttc, obj, msg):
        logging.info(
            "Received message for topic {}: '{}'".format(msg.topic, msg.payload)
        )

        selected_floors = json.loads(msg.payload)
        elevator_id = self.get_elevator_id(msg)

        # check if key exists, create new if not
        if elevator_id not in self.elevators:
            self.add_elevator(elevator_id)
        elevator = self.elevators[elevator_id]

        selected_floors = sorted(selected_floors)
        for f in selected_floors:
            # only add to queue if not selected already
            if f not in elevator["queue"]:
                elevator["queue"].append(f)

        queue = elevator["queue"]
        logging.info(f"elevator {elevator_id} destination queue {queue}")

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
        direction = self.get_call_button_direction(msg.topic)
        # set button pushed
        self.floors[source][direction] = True

        chosen_elevator = self.get_closest_idle_elevator(source)
        if chosen_elevator is None:
            chosen_elevator = self.get_closest_elevator(source, direction)

        topic = f"elevator/{chosen_elevator}/nextDestination"
        payload = str(source)
        self.mqttc.publish(topic, payload)
        logging.info(f"published to topic: '{topic}'; payload: '{payload}'")

    def get_call_button_direction(self, topic: str):
        # direction is last section in topic
        # floor/{level}/callButton/isPushed/{up | down}
        return topic.split("/")[-1]

    def start(self, host, port):
        self.mqttc = mqtt.Client()
        self.mqttc.connect(host, int(port))
        self.mqttc.on_message = self.on_message
        self.mqttc.on_connect = self.on_connect

        self.mqttc.loop_forever()


class Simulator:
    def __init__(self, loglevel, floor_count: int, elevator_count: int):
        random.seed()

        if not isinstance(loglevel, int):
            raise ValueError("Invalid log level: {}".format(loglevel))
        logging.basicConfig(level=loglevel)

        self.controller = ElevatorController(
            floor_count=floor_count, elevator_count=elevator_count
        )

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
    floor_count = os.getenv("floor_count")
    elevator_count = os.getenv("elevator_count")

    simulator = Simulator(
        getattr(logging, loglevel.upper()), int(floor_count), int(elevator_count)
    )
    simulator.start(host=host, port=port)
