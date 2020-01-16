import os
import json
import random
import logging
import argparse

from time import sleep

import paho.mqtt.client as mqtt
import topics

class Floor:

    def __init__(self, floor):
        self.floor = floor
        self.count = 0

    def on_message(self, mqttc, obj, msg):
        if int(msg.payload) == int(self.floor):
            logging.info("on my floor {}. reset!".format(self.floor))
            self.count = 0
            mqttc.publish("hola", True)

    def mqtt_init(self, host, port):
        self.mqttc = mqtt.Client()
        self.mqttc.connect(host, int(port))
        self.mqttc.on_message = self.on_message
        self.mqttc.subscribe(topics.elevators_current_position())
        self.mqttc.loop_start()

    def simulate_camera(self, count):
        logging.info("Simulating camera read; count={}".format(count))
        self.mqttc.publish(topics.camera_count(self.floor), json.dumps({"count": count}))

    def simulate_button_press(self, direction, count):
        logging.info("Simulating button press; direction={}, count={}".format(direction, count))
        self.mqttc.publish(topics.call_button(self.floor), json.dumps({"direction": direction, "count": count}))

class Simulator:

    def __init__(self, floor, loglevel):
        random.seed()

        if not isinstance(loglevel, int):
            raise ValueError('Invalid log level: {}'.format(loglevel))
        logging.basicConfig(level=loglevel)

        self.floor = Floor(floor)

    def start(self, simdata="", host="localhost", port=1883):
        logging.info("Starting simulation")

        self.floor.mqtt_init(host, port)

if __name__ == '__main__':
    argp = argparse.ArgumentParser(description="simulator for mqtt messages")

    argp.add_argument('-mqtthost', action="store", dest="host", default="localhost", help="default: localhost")
    argp.add_argument('-mqttport', action="store", dest="port", default=1883, help="default: 1883")
    argp.add_argument('-floor', action="store", dest="floor", default=-1, help="default: -1")
    argp.add_argument('-log', action="store", dest="log", default="WARNING", help="default: WARNING\nAvailable: INFO DEBUG WARNING ERROR CRITICAL")

    args = argp.parse_args()

    host = os.getenv('mqtt_host', args.host)
    port = os.getenv('mqtt_port', args.port)
    floor_num = os.getenv('floor', args.floor)
    loglevel = os.getenv('log_level', args.log)

    simulator = Simulator(floor_num, getattr(logging, loglevel.upper()))
    simulator.start(host=host, port=port)

    DIRECTIONS = ['up', 'down']
    # while True:
    #     simulator.floor.simulate_camera(random.randint(0, 10))
    #     sleep(1)
    #     simulator.floor.simulate_button_press(random.choice(DIRECTIONS), random.randint(0, 10))
    #     sleep(2)

    simulator.floor.simulate_button_press("up", random.randint(0, 10))
    sleep(2)