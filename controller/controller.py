# controller.py

import os
import logging
import argparse
import threading
import json
import time

import paho.mqtt.client as mqtt
from typing import List
from collections import deque
from cps_common.data import ElevatorData, FloorData


class Controller:
    def __init__(self):
        self.elevators: List[ElevatorData] = [ElevatorData(id) for id in range(0, 6)]
        self.floors: List[FloorData] = [FloorData(id) for id in range(0, 10)]
        self._callButtonEvent = threading.Event()

    def run(self, host: str = "localhost", port: int = 1883):
        # setup MQTT
        self.client = mqtt.Client("controller")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.connect(host, port)

        self.schedulerThread = threading.Thread(target=self.scheduler)
        self.schedulerThread.start()

        self.dispatcher_locks: List[threading.Condition] = []
        self.dispatcher_threads: List[threading.Thread] = []
        for id in range(0, 6):
            self.dispatcher_locks.append(
                threading.Condition()
            )  # lock for each elevator
            self.dispatcher_threads.append(
                threading.Thread(target=self.elevator_dispatcher, kwargs={"id": id})
            )
            self.dispatcher_threads[id].start()

        self.client.loop_forever()

    def on_connect(self, client, userdata, flags, rc):
        logging.info("connected to broker!")

        subscriptions = [
            ("elevator/+/status", self.on_elevator_status),
            ("elevator/+/actual_floor", self.on_elevator_actual_floor),
            ("elevator/+/capacity", self.on_elevator_capacity),
            ("elevator/+/selected_floors", self.on_elevator_selected_floors),
            ("floor/+/waiting_count", self.on_floor_waiting_count),
            ("floor/+/button_pressed/#", self.on_floor_button_pressed),
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
        # logging.info(f"New message from {msg.topic}")

        id = int(msg.topic.split("/")[1])
        elevator = self.elevators[id]
        elevator.status = msg.payload.decode("utf-8")
        # logging.debug(f"elevator {id} status {elevator.status}")

    def on_elevator_actual_floor(self, client, userdata, msg):
        # logging.info(f"New message from {msg.topic}")

        id = int(msg.topic.split("/")[1])
        elevator = self.elevators[id]
        elevator.floor = int(msg.payload)
        # logging.debug(f"elevator {id} actual floor {elevator.floor}")

        if elevator.queue and elevator.floor == elevator.queue[0]:
            elevator.queue.popleft()
            cv = self.dispatcher_locks[elevator.id]
            with cv:
                cv.notify()

    def on_elevator_capacity(self, client, userdata, msg):
        # logging.info(f"New message from {msg.topic}")

        id = int(msg.topic.split("/")[1])
        capacity = json.loads(msg.payload)

        elevator = self.elevators[id]
        elevator.actual_capacity = capacity["actual"]
        elevator.max_capacity = capacity["max"]
        # logging.debug(f"elevator {id} actual cap {elevator.actual_capacity}")
        # logging.debug(f"elevator {id} max cap {elevator.max_capacity}")

    def on_floor_waiting_count(self, client, userdata, msg):
        # logging.info(f"New message from {msg.topic}")

        id = int(msg.topic.split("/")[1])
        floor = self.floors[id]
        floor.waiting_count = int(msg.payload)
        # logging.debug(f"floor {id} waiting count {floor.waiting_count}")

    def on_floor_button_pressed(self, client, userdata, msg):
        # logging.info(f"New message from {msg.topic}")

        id = int(msg.topic.split("/")[1])
        floor = self.floors[id]
        # get last section of the topic: "up" or "down"
        direction = msg.topic.split("/")[-1]
        value = bool(msg.payload)
        # logging.debug(f"floor {id} button direction: {direction}; value: {value}")

        if direction == "up":
            floor.up_pressed = value
        elif direction == "down":
            floor.down_pressed = value
        else:
            logging.warning("unknown button direction received")

        self._callButtonEvent.set()

    def on_elevator_selected_floors(self, client, userdata, msg):
        id = int(msg.topic.split("/")[1])
        elevator = self.elevators[id]

        len_old = len(elevator.queue)

        selected = json.loads(msg.payload)
        for f in selected:
            f = int(f)
            if f not in elevator.queue:
                logging.debug(f"elevator {id} new selected floor {f}")
                # TODO: should double floor be allowed?
                # TODO: append based on direction of elevator
                elevator.queue.append(f)
        self.client.publish(
            f"simulation/elevator/{elevator.id}/queue",
            json.dumps(elevator.queue, cls=DequeEncoder),
            qos=0,
        )

        # notify scheduler thread to update schedule
        self._callButtonEvent.set()
        # notify dispatcher if queue not empty and new dest added to queue
        if elevator.queue and len_old != len(elevator.queue):
            logging.debug(f"elevator {elevator.id} queue: {list(elevator.queue)}")
            cv = self.dispatcher_locks[id]
            with cv:
                cv.notify()

    def try_get_idle_elevator(self) -> ElevatorData:
        # try get elevator with empty queue
        for e in self.elevators:
            if len(e.queue) == 0:
                return e
        return None

    def get_nearest_elevator(self, source_floor: int) -> ElevatorData:
        # try get elevator with empty queue
        distance = [100 for e in range(0, 10)]  # start with high distance

        for i, e in enumerate(self.elevators):
            # TODO: direction of elevator important?
            distance[i] = abs(e.floor - source_floor)
        return self.elevators[distance.index(min(distance))]

    def select_elevator(self, source_floor: int) -> ElevatorData:
        elevator = self.try_get_idle_elevator()
        if elevator is not None:
            return elevator

        # no elevator with empty queue
        return self.get_nearest_elevator(source_floor)

    def get_called_floor(self) -> int:
        for f in self.floors:
            if f.up_pressed or f.down_pressed:
                return f.id
        return None

    def scheduler(self):
        logging.debug(f"Start Scheduling Thread")
        t = threading.currentThread()
        while getattr(t, "do_run", True):
            self._callButtonEvent.wait()
            source_floor = self.get_called_floor()
            if source_floor is None:
                continue
            elevator = self.select_elevator(source_floor)
            assert isinstance(elevator, ElevatorData)
            if (source_floor not in elevator.queue) and (
                source_floor != elevator.floor
            ):
                elevator.queue.append(source_floor)
                cv = self.dispatcher_locks[elevator.id]
                with cv:
                    cv.notify_all()
            self.client.publish(
                f"simulation/elevator/{elevator.id}/queue",
                json.dumps(elevator.queue, cls=DequeEncoder),
                qos=0,
            )

    def elevator_dispatcher(self, id: int):
        logging.debug(f"Start Dispatcher Thread")
        t = threading.currentThread()

        elevator = self.elevators[id]
        cv = self.dispatcher_locks[id]
        while getattr(t, "do_run", True):
            self.client.publish(
                f"simulation/elevator/{elevator.id}/queue",
                json.dumps(elevator.queue, cls=DequeEncoder),
                qos=0,
            )
            logging.debug(f"elevator {elevator.id} queue: {elevator.queue}")

            while len(elevator.queue) == 0:
                with cv:
                    cv.wait()

            logging.debug(
                f"elevator {elevator.id} next_floor: {int(elevator.queue[0])}"
            )
            self.client.publish(
                f"elevator/{elevator.id}/next_floor", (elevator.queue[0]), qos=0,
            )
            time.sleep(1)


class DequeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, deque):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


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
