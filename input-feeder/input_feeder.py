#!/usr/bin/env python3
# input_feeder.py

import argparse
import asyncio
import os
import yaml
import json
from time import sleep
import paho.mqtt.client as mqtt

scheduled_msg = []


def init_mqtt(host: str, port: int) -> mqtt.Client:
    mqttc = mqtt.Client(client_id="input_feeder")
    mqttc.on_publish = on_publish
    mqttc.connect(host, port)
    return mqttc


def on_publish(client, userdata, mid):
    for m in scheduled_msg:
        if m.mid == mid:
            scheduled_msg.remove(m)
            break


def get_floor_topic(floor: int):
    return f"simulation/floor/{floor}/passenger_waiting"


async def delayed_publish(delay: int, floor: int, passengers):
    """
    :param delay: the delay before publish
    :param floor: start floor of the passengers
    :param passengers: list of passengers arriving
    """
    passengers = [
        {"start": floor, "destination": int(p["destination"])} for p in passengers
    ]

    topic = get_floor_topic(floor)

    await asyncio.sleep(delay)
    scheduled_msg.append(mqttc.publish(topic, json.dumps(passengers), qos=2))


async def main(samples: str):
    schedule = []
    samples = yaml.load(samples, Loader=yaml.BaseLoader)

    FLOOR_COUNT = 10
    expected = {str(i): 0 for i in range(0, FLOOR_COUNT)}

    for s in samples:
        time = int(s["time"])
        for p in s["passengers"]:
            start_floor = int(p["start"])
            passengers = []
            for destination, count in p["destinations"].items():
                passengers.extend(
                    [
                        {"start": start_floor, "destination": destination}
                        for i in range(0, int(count))
                    ]
                )

            schedule.append(delayed_publish(time, start_floor, passengers))
            for p in passengers:
                expected[str(p["destination"])] += 1
    mqttc.publish("simulation/passengers/expected", json.dumps(expected), qos=2)
    await asyncio.gather(*schedule)

    while len(scheduled_msg) != 0:
        await asyncio.sleep(1)
    print(f"finished feeding inputs: {expected}")


async def main_single(start: int, dst: int):
    passenger = {"start": start, "destination": dst}
    await delayed_publish(0, start, [passenger])
    mqttc.publish("simulation/passengers/expected", json.dumps({str(dst): 1}), qos=2)

    while len(scheduled_msg) != 0:
        await asyncio.sleep(1)
    print(f"finished feeding single input: start: {start}, destination: {dst}")


if __name__ == "__main__":
    argp = argparse.ArgumentParser(description="simulator for mqtt messages")
    argp.add_argument(
        "-host",
        action="store",
        dest="host",
        default="localhost",
        help="default: localhost",
    )
    argp.add_argument(
        "-port", action="store", dest="port", default=1883, help="default: publish1883"
    )
    argp.add_argument(
        "-samples", action="store", dest="samples", help="use passenger samples",
    )

    argp.add_argument(
        "-single",
        action="store",
        dest="single",
        help="single passenger in form of '(START,END)'",
    )
    args = argp.parse_args()

    host = os.getenv("mqtt_host", args.host)
    port = os.getenv("mqtt_port", args.port)
    samples_file = os.getenv("samples_list", args.samples)

    mqttc = init_mqtt(host, port)
    mqttc.loop_start()

    if args.single:
        params = args.single.split(",")
        start = int(params[0])
        dst = int(params[1])
        asyncio.run(main_single(start, dst))
    else:
        samples = open(samples_file, "r").read()
        asyncio.run(main(samples))

    mqttc.disconnect()
