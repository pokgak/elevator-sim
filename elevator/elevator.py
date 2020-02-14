# elevator.py

import os
import logging
import argparse
import threading
import time
from cps_common.data import Passenger
from typing import List
import json

import paho.mqtt.client as mqtt

class Elevator:

    def __init__(self, id: int, start_floor: int = 0):
        self.id = id
        self.maxCap=20 #todo as parameter
        self.actualCap=0
        self.destinations = set()
        self.nextFloor=start_floor
        self.currentFloor=0
        self.door_status="open"
        self.passenger_list: List[Passenger]=[]

        self._lock = threading.Lock()
        self._newNextFloor = threading.Event()

        self.client = mqtt.Client(f"elevator{self.id}")

    def run(self, host: str = "localhost", port: int = 1883):
        # setup MQTT
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.will_set(topic=f"elevator/{self.id}/status", payload="offline", qos=2)
        self.client.connect(host, port)

        self.healthThread = threading.Thread(target=self.health)
        self.capacityThread = threading.Thread(target=self.capacity)
        self.floorThread = threading.Thread(target=self.floor)
        self.moveThread = threading.Thread(target=self.move)

        self.healthThread.start()
        self.capacityThread.start()
        self.floorThread.start()
        self.moveThread.start()

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

    def health(self):
        t = threading.currentThread()
        while getattr(t, "do_run", True):
            self.client.publish(topic=f"elevator/{self.id}/status", payload="online", qos=1)
            time.sleep(60)     

    def capacity(self):
        t = threading.currentThread()
        while getattr(t, "do_run", True):
            self.client.publish(topic=f"elevator/{self.id}/capacity", payload=f'{{"max": {self.maxCap}, "actual": {self.actualCap}}}', qos=1)
            time.sleep(1)  
    
    def floor(self):
        t = threading.currentThread()
        while getattr(t, "do_run", True):
            self.client.publish(topic=f"elevator/{self.id}/actual_floor", payload=f"{self.currentFloor}", qos=1)
            self.client.publish(topic=f"elevator/{self.id}/door", payload=f"{self.door_status}", qos=1)
            time.sleep(1)  

    def on_disconnect(self, client, userdata, rc):
        logging.info("disconnected from broker")

    def on_elevator_next_floor(self, client, userdata, msg):
        logging.info(f"New message from {msg.topic}")
        next_floor = int(msg.payload)

        with self._lock:
            if self.nextFloor != next_floor:
                self.nextFloor = next_floor
                self.destinations.add(next_floor)
                self._newNextFloor.set()

    def on_simulation_passenger(self, client, userdata, msg):
        logging.info(f"New message from {msg.topic}")
        
        new_passenger = json.loads(msg.payload)

        for p in new_passenger:
            p = Passenger.from_json_dict(p)
            p.log_enter_elevator()
            self.destinations.add(p.end_floor)
            self.passenger_list.append(p)
            self.actualCap += 1

        self.client.publish(topic=f"elevator/{self.id}/selected_floors", payload=json.dumps(self.destinations, cls=SetEncoder), qos=1)

    def move(self):
        t = threading.currentThread()
        while getattr(t, "do_run", True):
            self._newNextFloor.wait()
            while self.currentFloor != self.nextFloor:
                time.sleep(3)
                self.door_status="closed"
                with self._lock:
                    if self.currentFloor > self.nextFloor:
                        self.currentFloor -= 1
                    elif self.currentFloor < self.nextFloor:
                        self.currentFloor += 1
                    
                    if self.currentFloor == self.nextFloor:
                        leaving = [p for p in self.passenger_list if p.end_floor == self.currentFloor]
                        self.passenger_list = [p for p in self.passenger_list if p not in leaving]
                        msg = []
                        for p in leaving:
                            p.log_leave_elevator()
                            self.actualCap -= 1
                            msg.append(p.to_json())
                        self.destinations.discard(self.currentFloor)
                        self.door_status="open"
                        self.client.publish(topic=f"simulation/floor/{self.currentFloor}/passenger_arrived", payload=json.dumps(msg), qos=2)


class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


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
        "-id", action="store", dest="elevatorid", default=0, help="Elevator ID",
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
