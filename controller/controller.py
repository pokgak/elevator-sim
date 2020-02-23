# controller.py

import os
import logging
import argparse
import threading
import json
import time

import paho.mqtt.client as mqtt
from typing import List, Deque
from collections import deque
from cps_common.data import ElevatorData, FloorData


# mode
SMART = "smart"
DUMB = "dumb"

MULTIPLE_ELEVATOR_THRESHOLD = 10

# direction
UP = "up"
DOWN = "down"


class Controller:
    def __init__(self, mode: str):
        self.mode = mode
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
        if elevator.old_floor != elevator.floor:
            elevator.old_floor = elevator.floor

        if elevator.floor > elevator.old_floor:
            elevator.direction = UP
        elif elevator.floor < elevator.old_floor:
            elevator.direction = DOWN

        if elevator.queue and elevator.floor == elevator.queue[0]:
            # resets call button when an elevator is driving in that direction
            floor = self.floors[elevator.floor]
            if elevator.direction == UP:
                floor.up_pressed = False
            elif elevator.direction == DOWN:
                floor.down_pressed = False

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
        logging.debug(f"floor {id} button direction: {direction}; value: {value}")

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

        selected = json.loads(msg.payload)
        # logging.debug(f"elevator {id} selected floors: {selected}")
        if elevator.actual_capacity < elevator.max_capacity:
            elevator.queue += [f for f in selected if f not in elevator.queue]
        else:
            logging.debug(
                f"clearing elevator {elevator.id} queue; added {selected} to queue"
            )
            # ignore calling floor, send passenger in elevator first
            elevator.queue = deque(selected)

        elevator.queue = self.sort_queue(
            elevator.direction, elevator.floor, elevator.queue
        )
        logging.debug(f"sorted queue: {elevator.queue}")

        self.client.publish(
            f"simulation/elevator/{elevator.id}/queue",
            json.dumps(elevator.queue, cls=DequeEncoder),
            qos=0,
        )

        cv = self.dispatcher_locks[id]
        with cv:
            cv.notify()

        # notify scheduler thread to update schedule
        # self._callButtonEvent.set()

    def sort_queue(
        self, direction: str, current_floor: int, q: Deque[int]
    ) -> Deque[int]:
        # to sort: [8, 1, 6, 7, 2, 3]
        # current floor: 5
        # upper: [6, 7, 8]
        # lower: [3, 2, 1]
        # if direction UP: [6, 7, 8, 3, 2, 1]
        # if direction DOWN: [3, 2, 1, 6, 7, 8]

        # check queue empty
        if not q:
            logging.warning("queue to sort is empty")
            return q

        # separate the queue to upper and lower floor compared to the current floor
        upper = sorted([f for f in q if f > current_floor])
        # reverse lower because when at higher floor we want to go down
        # e.g. current: 9; queue: [8, 7, 6] not [6, 7, 8]
        lower = sorted([f for f in q if f < current_floor])
        lower.reverse()

        # if at lowest floor
        if not lower:
            return deque(upper)
        # or at highest floor
        if not upper:
            return deque(lower)
        # else we need to combine both upper and lower
        direction = "UP"  # FIXME: always up for now
        if direction == "UP":
            return deque(upper + lower)
        else:
            return deque(lower + upper)

    def try_get_idle_elevator(self) -> ElevatorData:
        # try get elevator with empty queue
        for e in self.elevators:
            if len(e.queue) == 0:
                return e
        return None

    def try_get_empty_elevator(self):
        for e in self.elevators:
            if e.actual_capacity == 0:
                e.queue.clear()
                return e
        return None

    def get_nearest_elevator(self, source_floor: int) -> ElevatorData:
        # try get elevator with empty queue
        distance = [100 for e in range(0, 10)]  # start with high distance

        for i, e in enumerate(self.elevators):
            # TODO: direction of elevator important?
            distance[i] = abs(e.floor - source_floor)

        # TODO: only return if elevator not full (max_cap < 20)
        return self.elevators[distance.index(min(distance))]

    def select_elevator(self, source_floor: int) -> ElevatorData:
        elevator = self.try_get_idle_elevator()
        if elevator is not None:
            return elevator

        elevator = self.try_get_empty_elevator()
        if elevator is not None:
            return elevator

        # no elevator with empty queue
        return self.get_nearest_elevator(source_floor)

    def get_called_floor_dumb(self) -> int:
        combined_queue = []
        for e in self.elevators:
            combined_queue += e.queue

        pressed_floors = []
        for f in self.floors:
            if f.id in combined_queue:
                continue
            if f.up_pressed or f.down_pressed:
                pressed_floors.append({"id": f.id, "count": f.waiting_count})
        max_count = max(pressed_floors, default=None, key=compare_waiting_count)
        if max_count is not None:
            # logging.debug(f"max_count floor: {max_count}")
            return max_count["id"]

        return None

    def get_called_floor_smart(self) -> int:
        combined_queue = []
        for e in self.elevators:
            combined_queue += e.queue

        pressed_floors = []
        for f in self.floors:
            if (
                f.id in combined_queue
                and f.waiting_count <= MULTIPLE_ELEVATOR_THRESHOLD
            ):
                continue
            if f.up_pressed or f.down_pressed:
                pressed_floors.append({"id": f.id, "count": f.waiting_count})
        max_count = max(pressed_floors, default=None, key=compare_waiting_count)
        if max_count is not None:
            # logging.debug(f"max_count floor: {max_count}")
            return max_count["id"]
        return None

    def scheduler(self):
        logging.debug(f"Start Scheduling Thread")
        t = threading.currentThread()
        while getattr(t, "do_run", True):
            self._callButtonEvent.wait()
            if self.mode == SMART:
                source_floor = self.get_called_floor_smart()
            else:
                source_floor = self.get_called_floor_dumb()
            if source_floor is None:
                continue

            elevator = self.select_elevator(source_floor)
            assert isinstance(elevator, ElevatorData)
            if (
                (source_floor not in elevator.queue)
                and (source_floor != elevator.floor)
                # and (self.floors[source_floor].waiting_count > 0)  # TODO: smart toggle
                and (elevator.actual_capacity < elevator.max_capacity)
            ):
                elevator.queue.append(source_floor)
                cv = self.dispatcher_locks[elevator.id]
                with cv:
                    cv.notify()

            self.client.publish(
                f"simulation/elevator/{elevator.id}/queue",
                json.dumps(elevator.queue, cls=DequeEncoder),
                qos=0,
            )
            # time.sleep(0.5)

    def elevator_dispatcher(self, id: int):
        logging.debug(f"Start Dispatcher Thread")
        t = threading.currentThread()

        elevator = self.elevators[id]
        cv = self.dispatcher_locks[id]
        while getattr(t, "do_run", True):
            while len(elevator.queue) == 0:
                with cv:
                    cv.wait()

            self.client.publish(
                f"simulation/elevator/{elevator.id}/queue",
                json.dumps(elevator.queue, cls=DequeEncoder),
                qos=0,
            )
            # logging.debug(f"elevator {elevator.id} queue: {elevator.queue}")

            next_floor: int = int(elevator.queue[0])
            # logging.debug(f"elevator {elevator.id} next_floor: {next_floor}")
            self.client.publish(
                f"elevator/{elevator.id}/next_floor", next_floor, qos=0,
            )

            time.sleep(0.5)


class DequeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, deque):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


def compare_waiting_count(f):
    return f["count"]


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
    argp.add_argument(
        "-mode",
        action="store",
        dest="mode",
        default="smart",
        help="default: smart\nAvailable: smart | dumb",
    )

    args = argp.parse_args()

    host = os.getenv("mqtt_host", args.host)
    port = os.getenv("mqtt_port", args.port)
    loglevel = os.getenv("log_level", args.log)
    mode = os.getenv("mode", args.log).lower()

    logging.basicConfig(level=getattr(logging, loglevel.upper()))

    logging.info("Starting controller")

    controller = Controller(mode)
    controller.run(host=host, port=int(port))

    logging.info("Exited controller")
