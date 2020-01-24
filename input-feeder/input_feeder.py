#!/usr/bin/env python3
# input_feeder.py

import argparse
import asyncio
import os
import time
import yaml
import json

from typing import List

import paho.mqtt.client as mqtt


def init_mqtt(host: str, port: int) -> mqtt.Client:
    print("init mqtt")
    mqttc = mqtt.Client()
    mqttc.on_connect = on_connect
    mqttc.connect(host, port)
    return mqttc


def on_connect(client, userdata, flags, rc):
    print("connected")

def get_floor_topic(floor: int):
    return f"simulation/config/passengerList/floor/{floor}"

async def delayed_publish(delay: int, floor: int, passengers):
    """
    :param delay: the delay before publish
    :param floor: start floor of the passengers
    :param passengers: list of passengers arriving
    """
    payload = passengers

    topic = get_floor_topic(floor)

    await asyncio.sleep(delay)
    print(f"publishing passengers: {payload}")
    mqttc.publish(topic, json.dumps(payload))
    print(f"published passenger: {payload}; start: {floor}")

async def main(samples: str):
    schedule = []
    samples = yaml.load(samples, Loader=yaml.BaseLoader)

    for s in samples:
        time = int(s["time"])
        for f in s["floors"]:
            start_floor = int(f["start"])
            passengers = f["passengers"]
            schedule.append(delayed_publish(time , start_floor, passengers))

    await asyncio.gather(*schedule)
    print("finished feeding inputs")


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
        "-samples",
        action="store",
        dest="samples",
        default="samples/simple_scenario.yaml",
        help="default: samples/simple_scenario.yaml",
    )
    args = argp.parse_args()

    host = os.getenv("mqtt_host", args.host)
    port = os.getenv("mqtt_port", args.port)
    samples_file = os.getenv("samples_list", args.samples)

    mqttc = init_mqtt(host, port)

    # print("Sleeping for 3 seconds before start sending inputs")
    # time.sleep(3)
    print("Start!")
    samples = open(samples_file, 'r').read()
    asyncio.run(main(samples))

    mqttc.disconnect()
