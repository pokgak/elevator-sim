# recorder.py

import os
import json
import csv
import logging
import argparse
import paho.mqtt.client as mqtt
from datetime import datetime as dt
from cps_common.data import Passenger
from typing import List


def on_connect(client, userdata, flags, rc):
    logging.debug("CONNECTED")
    client.subscribe("simulation/stop")
    client.message_callback_add("simulation/stop", on_stop)

    client.subscribe("record/floor/+/passenger_arrived", qos=0)
    client.message_callback_add("record/floor/+/passenger_arrived", on_record)


def on_record(client, userdata, msg):
    arrived: List[Passenger] = json.loads(
        msg.payload, object_hook=Passenger.from_json_dict
    )
    assert isinstance(arrived, list)

    for p in arrived:
        logging.debug(f"wrote {p.to_dict()}")
        writer.writerow(p.to_dict())
        resfile.flush()


def on_stop(client, userdata, msg):
    logging.debug("STOPPING SIMULATION")
    client.disconnect()


def on_disconnect(client, userdata, rc):
    logging.debug("DISCONNECT")
    resfile.close()


if __name__ == "__main__":
    argp = argparse.ArgumentParser(description="Data Recorder")
    argp.add_argument(
        "-host",
        action="store",
        dest="host",
        default="localhost",
        help="default: localhost",
    )
    argp.add_argument(
        "-resdir",
        action="store",
        dest="resdir",
        default="logs",
        help="default: logs",
    )
    argp.add_argument(
        "-log",
        action="store",
        dest="log",
        default="DEBUG",
        help="default: ERROR\nAvailable: INFO DEBUG WARNING ERROR CRITICAL",
    )

    args = argp.parse_args()
    host = os.getenv("mqtt_host", args.host)
    resdir = os.getenv("resdir", args.resdir)
    loglevel = os.getenv("log_level", args.log)

    logging.basicConfig(level=getattr(logging, loglevel.upper()))

    if not os.path.exists(resdir):
        os.makedirs(resdir)
    resname = resdir + "/log-" + dt.now().strftime("%F-%H:%M:%S") + ".csv"
    logging.debug(f"writing log to {resname}")
    resfile = open(resname, mode="x", newline="")
    headers = [
        "id",
        "start_floor",
        "end_floor",
        "start_timestamp",
        "enter_elevator_timestamp",
        "leave_elevator_timestamp",
        "end_timestamp",
    ]
    writer = csv.DictWriter(resfile, headers)
    writer.writeheader()
    resfile.flush()

    client = mqtt.Client(client_id="recorder")
    client.on_connect = on_connect
    client.connect(host)

    client.loop_forever()
    logging.debug("FINISHED")
