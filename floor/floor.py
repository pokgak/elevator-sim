#!/usr/bin/env python3

import argparse
import datetime
import json
import logging
import os
import time
from collections import deque

import paho.mqtt.client as mqtt


class Floor:
    def __init__(self, level: int):
        logging.info("ELEVATOR INIT")
        self.orig_params = {
            "level": level,
        }

        self.mqttc: mqtt.Client = None
        self.level = level

        self.passenger_queue = deque()
        self.arrived_passengers = []

        self.up_pressed = False
        self.down_pressed = False

        self.client_id = f"floor{level}"

    def start(self, hostname: str = "mqtt", port: int = 1883):
        self.mqttc.on_message = self.on_message
        self.mqttc.on_connect = self.on_connect
        logging.info("Connecting to broker. Please wait...")
        self.mqttc.connect(hostname, port)
        logging.info("starting MQTT loop")

    def reset(self):
        Floor.__init__(
            self, self.orig_params["level"],
        )
        time.sleep(1)
        self.start()

    def on_reset(self, client, userdata, msg):
        logging.info("resetting to initial state")
        time.sleep(2)
        self.reset()
        logging.info("reset finished")

    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected to broker!")

        # (topic, callback)
        topics = [
            (f"elevator/+/status", self.elevator_status_cb),
            (
                f"simulation/config/passengerList/floor/{self.level}",
                self.config_passenger_list_cb,
            ),
            ("simulation/reset", self.on_reset),
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

        callButton pushed message is sent everytime new config_passenger_list_cb ist called

        Format of expected JSON message:

        [
            {
                "start": int,
                "destination": int,
            }
        ]
        """

        passenger_list = json.loads(message.payload)
        for p in passenger_list:
            p["start_time"] = datetime.datetime.now().strftime("%H:%M:%S.%f")
        self.passenger_queue += passenger_list
        self.push_call_button(passenger_list)

    def push_call_button(self, passenger_list):
        for p in passenger_list:
            destination = int(p["destination"])
            if not self.up_pressed:
                self.up_pressed = destination > self.level
            if not self.down_pressed:
                self.down_pressed = destination < self.level

        logging.info(
            f"up pressed: {self.up_pressed}, down pressed: {self.down_pressed}"
        )
        logging.info(f"passenger queue current status: {self.passenger_queue}")

        if self.up_pressed:
            self.mqttc.publish(f"floor/{self.level}/callButton/isPushed/up", "true")
            logging.info(f"published callButton pushed up: true")
        if self.down_pressed:
            self.mqttc.publish(f"floor/{self.level}/callButton/isPushed/down", "true")
            logging.info(f"published callButton pushed down: true")

    def publish_arrived_passengers(self, level: int):
        topic = f"floor/{level}/arrived_passenger"

        count = len(self.arrived_passengers)
        # total in miliseconds
        total_wait_time = 0
        for p in self.arrived_passengers:
            start = datetime.datetime.strptime(str(p["start_time"]), "%H:%M:%S.%f")
            end = datetime.datetime.strptime(str(p["arrived_time"]), "%H:%M:%S.%f")
            diff = end - start
            diff_msec = diff / datetime.timedelta(milliseconds=1)
            total_wait_time += diff_msec

        average_msec = total_wait_time / count

        payload = {
            "count": count,
            "total_wait_time": str(datetime.timedelta(milliseconds=total_wait_time)),
            "average_wait_time": str(datetime.timedelta(milliseconds=average_msec)),
        }
        self.mqttc.publish(topic, json.dumps(payload))
        logging.info(f"published arrived passengers: {payload}")

    def elevator_status_cb(self, client, userdata, message):
        elevator = json.loads(message.payload)
        # skip if not at current floor
        # ignore driving up status
        if elevator["current_position"] != self.level:
            return

        # FIXME: determine which direction the elevator is going to and only disable button
        # with same direction
        self.up_pressed = False
        self.down_pressed = False

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
            "exit_list": [],
        }
        """

        if elevator["state"] == "EXIT":
            exit_list = elevator["exit_list"]
            for p in exit_list:
                p["arrived_time"] = datetime.datetime.now().strftime("%H:%M:%S.%f")
            self.arrived_passengers.extend(exit_list)
            logging.info(
                f"list arrived passengers: count: {len(self.arrived_passengers)}; list: {self.arrived_passengers}"
            )
            self.publish_arrived_passengers(self.level)

        # reply with passenger enter
        if len(self.passenger_queue) != 0:
            available_capacity = elevator["max_capacity"] - elevator["current_capacity"]
            using = min(len(self.passenger_queue), available_capacity)
            logging.info(
                f"enter_list count: {using}; popping in range {range(0, using)}"
            )
            enter_list = [self.passenger_queue.popleft() for n in range(0, using)]

            topic = f"elevator/{self.get_elevator_id(message)}/passengerEnter"
            payload = {"floor": self.level, "enter_list": enter_list}
            logging.info(
                f"sending passenger entering list to elevator {self.get_elevator_id(message)}; payload: {payload}"
            )
            self.mqttc.publish(topic, json.dumps(payload))

        # resend callButton message if there is still passengers in queue after
        # the elevator left
        if (elevator["state"] == "UP" or elevator["state"] == "DOWN") and len(
            self.passenger_queue
        ) > 0:
            self.push_call_button(self.passenger_queue)

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
    floor.mqttc = mqtt.Client(client_id=f"floor{floor_level}")
    floor.start(hostname=host, port=int(port))
    floor.mqttc.loop_forever()
