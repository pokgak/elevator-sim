# async_mqtt.py

import asyncio
import socket
import json
import paho.mqtt.client as mqtt

from dashboard import DashboardUI
from components import ElevatorUI, FloorUI, FLOOR_COUNT


class AsyncioHelper:
    def __init__(self, loop, client):
        self.loop = loop
        self.client = client
        self.client.on_socket_open = self.on_socket_open
        self.client.on_socket_close = self.on_socket_close
        self.client.on_socket_register_write = self.on_socket_register_write
        self.client.on_socket_unregister_write = self.on_socket_unregister_write

    def on_socket_open(self, client, userdata, sock):
        def cb():
            client.loop_read()

        self.loop.add_reader(sock, cb)
        self.misc = self.loop.create_task(self.misc_loop())

    def on_socket_close(self, client, userdata, sock):
        self.loop.remove_reader(sock)
        self.misc.cancel()

    def on_socket_register_write(self, client, userdata, sock):
        def cb():
            client.loop_write()

        self.loop.add_writer(sock, cb)

    def on_socket_unregister_write(self, client, userdata, sock):
        self.loop.remove_writer(sock)

    async def misc_loop(self):
        while self.client.loop_misc() == mqtt.MQTT_ERR_SUCCESS:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break


class AsyncMQTT:

    client: mqtt.Client

    def __init__(self, loop, dashboard: DashboardUI):
        self.loop = loop
        self.dashboard = dashboard
        self.client_id = "dashboard"

        self.client = mqtt.Client(client_id=self.client_id)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # (topic, callback)
        callbacks = [
            ("floor/+/waiting_count", self.on_floor_waiting_count),
            ("elevator/+/actual_floor", self.on_elevator_actual_floor),
            ("elevator/+/capacity", self.on_elevator_capacity),
            ("elevator/+/queue", self.on_elevator_queue),
            ("simulation/floor/+/passenger_arrived", self.on_passenger_arrived),
        ]

        for c in callbacks:
            self.client.message_callback_add(c[0], c[1])

        AsyncioHelper(self.loop, self.client)

        self.client.connect("localhost", 1883)
        self.client.socket().setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2048)

    def on_connect(self, client, userdata, flags, rc):
        client.subscribe("#")

    def on_floor_waiting_count(self, client, userdata, msg):
        floor = int(msg.topic.split("/")[1])
        if floor >= FLOOR_COUNT:
            # ignore error and exit
            return

        count = json.loads(msg.payload)
        assert isinstance(count, int)

        floor: FloorUI = self.dashboard.get_floor(floor)
        floor.set_waiting_count(count)

    def on_elevator_actual_floor(self, client, userdata, msg):
        pass

    def on_elevator_capacity(self, client, userdata, msg):
        pass

    def on_elevator_queue(self, client, userdata, msg):
        pass

    def on_passenger_arrived(self, client, userdata, msg):
        pass

    # def on_expected_passengers(self, client, userdata, msg):
    #     expected = json.loads(msg.payload)
    #     for f in expected.keys():
    #         self.dashboard.set_passenger_count(int(f), expected=expected[f])

    # def on_arrived_passenger(self, client, userdata, msg):
    #     floor_level = int(msg.topic.split("/")[1])
    #     payload = json.loads(msg.payload)

    #     # order is important here. Average time needs the updated passenger count
    #     self.dashboard.set_passenger_count(floor_level, arrived=payload["count"])
    #     self.dashboard.set_wait_time(floor_level, payload["wait_time"])

    # def on_elevator_status(self, client, userdata, msg):
    #     id = int(msg.topic.split("/")[1])
    #     payload: dict = json.loads(msg.payload)

    #     elevator: ElevatorUI = self.dashboard.get_elevator(id)
    #     state = str(payload["state"])
    #     capacity = int(payload["current_capacity"])
    #     position = int(payload["current_position"])

    #     elevator.set_statebox_text(state=state, capacity=capacity)
    #     elevator.set_position(position)

    # def on_queue_update(self, client, userdata, msg):
    #     id = int(msg.topic.split("/")[1])
    #     queue_list: str = str([int(dst) for dst in json.loads(msg.payload)])

    #     self.dashboard.set_queue(id, queue_list)

    # def on_new_passengers(self, client, userdata, msg):
    #     level = int(msg.topic.split("/")[4])
    #     passenger_list: dict = json.loads(msg.payload)

    #     floor: FloorUI = self.dashboard.get_floor(level)
    #     floor.set_waiting_count(floor.get_waiting_count() + len(passenger_list))

    # def on_passenger_enter(self, client, userdata, msg):
    #     payload: dict = json.loads(msg.payload)
    #     level = payload["floor"]
    #     enter_count = len(payload["enter_list"])
    #     if enter_count <= 0:
    #         return

    #     floor: FloorUI = self.dashboard.get_floor(level)
    #     floor.set_waiting_count(floor.get_waiting_count() - enter_count)

    #     id = int(msg.topic.split("/")[1])
    #     elevator: ElevatorUI = self.dashboard.get_elevator(id)
    #     capacity = elevator.get_capacity() + enter_count
    #     elevator.set_statebox_text(state="ENTER", capacity=capacity)

    def on_message(self, client, userdata, msg):
        pass
