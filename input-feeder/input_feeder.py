#!/bin/env python3
# input_feeder.py

import argparse
import asyncio
import os
import time

import paho.mqtt.client as mqtt


def init_mqtt(host: str, port: int) -> mqtt.Client:
    print("init mqtt")
    mqttc = mqtt.Client()
    mqttc.on_connect = on_connect
    mqttc.connect(host, port)
    return mqttc


def on_connect(client, userdata, flags, rc):
    print("connected")


async def delayed_publish(delay: int, topic: str, msg: str):
    # print(f"wait to publish topic: {topic}; msg: {msg}")
    await asyncio.sleep(delay)
    mqttc.publish(topic, msg)
    print(f"published topic: {topic}; msg: {msg}")


async def main(samples_file):
    import aiofiles
    import json

    schedule = []
    async with aiofiles.open(samples_file) as f:
        for i in json.loads(await f.read()):
            schedule.append(delayed_publish(i["time"], i["topic"], json.dumps(i["message"])))
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
        default="samples/simple_scenario.json",
        help="default: samples/simple_scenario.json",
    )
    args = argp.parse_args()

    host = os.getenv("mqtt_host", args.host)
    port = os.getenv("mqtt_port", args.port)
    samples_file = os.getenv("samples_list", args.samples)

    mqttc = init_mqtt(host, port)

    print("Sleeping for 3 seconds before start sending inputs")
    time.sleep(3)
    print("Start!")
    asyncio.run(main(samples_file))

    mqttc.disconnect()
