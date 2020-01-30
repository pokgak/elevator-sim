import os
import urwid
import asyncio
import socket
import json
import paho.mqtt.client as mqtt

FLOOR_OFFSET = 2
FLOOR_COUNT = 10
ELEVATOR_COUNT = 6

STATUS_HEIGHT = FLOOR_OFFSET * FLOOR_COUNT + 3
STATISTICS_HEIGHT = 3

TEXTBOX_WIDTH = 8
ELEVATOR_WIDTH = TEXTBOX_WIDTH + 2

UPDATE_PERIOD = 0.1


class Floor(urwid.WidgetWrap):
    _sizing = frozenset(["box"])

    def __init__(self, floor: int, waiting_count: int = 0):
        self.floor: int = floor
        self.waiting_count: int = waiting_count
        self._selectable = False

        queue = urwid.Text(
            " 0" * waiting_count + f" [Floor: {self.floor}]",
            align="right",
            wrap="ellipsis",
        )
        queue = urwid.Padding(queue, right=1)
        queue = urwid.Filler(queue)
        super().__init__(queue)

    def get_waiting_count(self):
        return self.waiting_count

    def set_waiting_count(self, count: int):
        self.waiting_count = count
        self._w.base_widget.set_text(
            " 0" * self.waiting_count + f" [Floor: {self.floor}]"
        )


class Elevator(urwid.WidgetWrap):
    id: int

    def __init__(self, id: int, state="IDLE", position: int = 0, capacity: int = 0):
        self.position = position
        self.id = id
        self.capacity = capacity
        self.state = state

        statebox = urwid.Text(self.state + f"|{self.capacity}", align="center")
        statebox = urwid.LineBox(statebox, title=str(id))
        statebox = urwid.Filler(
            statebox,
            top=self.calculate_top_offset(position),
            bottom=self.calculate_bottom_offset(position),
            valign="top",
        )
        statebox._selectable = False
        super().__init__(statebox)

    def get_statebox(self) -> urwid.Text:
        return self._w.base_widget

    def set_statebox_text(self, state: str = None, capacity: int = None):
        if state is not None:
            self.state = state
        if capacity is not None:
            self.capacity = capacity
        self.get_statebox().set_text(f"{self.state}|{self.capacity}")

    def get_capacity(self) -> int:
        return self.capacity

    def get_state(self) -> str:
        return self.state

    def get_position(self) -> int:
        return self.position

    def set_position(self, position: int):
        self.position = position
        self._w = urwid.Filler(
            urwid.LineBox(self.get_statebox(), title=str(self.id)),
            top=self.calculate_top_offset(position),
            bottom=self.calculate_bottom_offset(position),
            valign="top",
        )

    def calculate_top_offset(self, position):
        return FLOOR_OFFSET * (FLOOR_COUNT - position - 1)

    def calculate_bottom_offset(self, position) -> int:
        return FLOOR_OFFSET * position


class Dashboard:

    palette = [
        # ("body", "dark cyan", "", "standout"),
        # ("focus", "dark red", "", "standout"),
        # ("head", "light red", "black"),
        ("hline", "white", "", "white"),
        ("vline", "black", "light gray", "standout"),
    ]

    asyncio_loop: asyncio.AbstractEventLoop
    urwid_loop: urwid.MainLoop

    def __init__(self):
        self.asyncio_loop = asyncio.get_event_loop()

        self.frame = self.build_dashboard()

        self.urwid_loop: urwid.MainLoop = urwid.MainLoop(
            self.frame,
            self.palette,
            event_loop=urwid.AsyncioEventLoop(loop=self.asyncio_loop),
        )

        # e = self.get_elevator(0)
        # self.asyncio_loop.call_later(1, e.set_state, "UP")
        # self.asyncio_loop.call_later(2, e.set_state, "DOWN")
        # self.asyncio_loop.call_later(3, e.set_state, "ENTER")
        # self.asyncio_loop.call_later(4, e.set_state, "EXIT")
        # self.asyncio_loop.call_later(5, e.set_state, "IDLE")

        # self.asyncio_loop.call_later(1, e.set_position, 1)
        # self.asyncio_loop.call_later(2, e.set_position, 2)
        # self.asyncio_loop.call_later(3, e.set_position, 3)
        # self.asyncio_loop.call_later(4, e.set_position, 4)
        # self.asyncio_loop.call_later(5, e.set_position, 0)

        # f = self.get_floor(3)
        # self.asyncio_loop.call_later(3, f.set_waiting_count, f.get_waiting_count() + 10)

        self.urwid_loop.set_alarm_in(UPDATE_PERIOD, self.update_screen, self.urwid_loop)

    def update_screen(self, loop, user_data=None):
        # urwid will automatically call draw_screen() function after this callback
        # we do this to control frequency of urwid update
        # change UPDATE_PERIOD to adjust
        self.urwid_loop.set_alarm_in(UPDATE_PERIOD, self.update_screen, self.urwid_loop)

    def build_dashboard(self):
        hline = urwid.AttrMap(urwid.SolidFill("\u2500"), "hline")
        vline = urwid.AttrMap(urwid.SolidFill("\u2502"), "vline")

        floor_height = 1
        floors = []
        floors.append(("fixed", 1, hline))
        for i in range(FLOOR_COUNT - 1, -1, -1):
            floors.append((floor_height, Floor(i)))
            floors.append(("fixed", 1, hline))

        self.floors = urwid.Pile(floors)
        floors = urwid.Filler(self.floors, "top")

        elevators = []
        for i in range(0, ELEVATOR_COUNT):
            elevators.append(("fixed", ELEVATOR_WIDTH, Elevator(id=i)))
        self.elevators = urwid.Columns(elevators, min_width=7)
        elevators = urwid.Filler(self.elevators, "top")

        status = urwid.Columns(
            [
                floors,
                ("fixed", 1, vline),
                (ELEVATOR_WIDTH * ELEVATOR_COUNT, self.elevators),
            ]
        )
        status = urwid.LineBox(status, title="Status")

        # TODO
        arrived_count = 10
        expected = 20
        total_wait_time = 100

        arrived_elements = [
            urwid.Text("Arrived Count", align="center"),
            urwid.Divider("-"),
            urwid.Text(f"Floor 0: 3/5 arrived | Floor 1: 3/5 arrived", align="center"),
            urwid.Text(f"Floor 2: 3/5 arrived | Floor 3: 3/5 arrived", align="center"),
            urwid.Text(f"Floor 4: 3/5 arrived | Floor 5: 3/5 arrived", align="center"),
            urwid.Text(f"Floor 6: 3/5 arrived | Floor 7: 3/5 arrived", align="center"),
            urwid.Text(f"Floor 8: 3/5 arrived | Floor 9: 3/5 arrived", align="center"),
            urwid.Divider(" "),
            urwid.Text(f"Total: {arrived_count}/{expected}", align="center"),
        ]
        arrived = urwid.Pile(arrived_elements)

        wait_time_title = urwid.Text("Waiting Time", align="center")
        wait_time_elements = [
            urwid.Text(f"Floor {f}: 0:00:00.000000", align="center")
            for f in range(0, FLOOR_COUNT)
        ]

        # separate the times to two sections left and right to save vertical space
        idx_middle = int(len(wait_time_elements) / 2)
        wait_time_left = urwid.Pile(wait_time_elements[:idx_middle])
        wait_time_right = urwid.Pile(wait_time_elements[idx_middle:])
        self.wait_time_values = urwid.Columns([wait_time_left, wait_time_right])

        self.wait_time_total = urwid.Text(
            f"Total: 0:00:00.000000 | Average: 0:00:00.000000", align="center",
        )
        wait_time = urwid.Pile(
            [
                wait_time_title,
                urwid.Divider("-"),
                self.wait_time_values,
                urwid.Divider(" "),
                self.wait_time_total,
            ]
        )

        queue_elements = [
            urwid.Text("Elevator Destination Queues", align="center"),
            urwid.Divider("-"),
        ]
        for i in range(0, ELEVATOR_COUNT):
            queue_elements.append(urwid.Text(f"E{i}: []"))
        self.queue = urwid.Pile(queue_elements)

        statistics = urwid.Columns([arrived, wait_time, self.queue])
        statistics = urwid.Filler(statistics)
        statistics = urwid.LineBox(statistics, title="Statistics")

        # FIXME: replace len(arrived_elements) with more general height
        return urwid.Pile(
            [(len(arrived_elements) + 2, statistics), (STATUS_HEIGHT, status)]
        )

    def get_wait_time(self, floor: int) -> urwid.Text:
        # left or right
        if floor < FLOOR_COUNT / 2:
            section = self.wait_time_values.contents[0][0]
            idx_in_section = floor
        else:
            section = self.wait_time_values.contents[1][0]
            idx_in_section = floor - FLOOR_COUNT / 2

        # access time in the section
        return section.contents[idx_in_section][0]

    def set_total_wait_time(self, floor: int, time: str):
        self.get_wait_time(floor).set_text(f"Floor {floor}: {time}")

    def get_queue(self, id: int) -> urwid.Text:
        # skip the header and divider '-'
        return self.queue.contents[2 + id][0]

    def set_queue(self, id: int, queue: str):
        self.get_queue(id).set_text(f"E{id}: {queue}")

    def get_elevator(self, idx: int) -> Elevator:
        return self.elevators.contents[idx][0]

    def get_floor(self, floor: int) -> Floor:
        # we access the list from behind
        # floor 0 is the "last" element in the list, with biggest floor at idx 0
        # multiply with 2 because between the floor there is the AttrMap element
        # for the line that we see in the dashboard
        # FIXME: try to combine the deco line as part of Floor
        idx = -(floor * 2) - 2
        return self.floors.contents[idx][0]

    def reset(self):
        for i in range(0, ELEVATOR_COUNT):
            self.get_elevator(i).set_position(0)
            self.get_elevator(i).set_statebox_text(state="IDLE", capacity=0)
        for i in range(0, FLOOR_COUNT):
            self.get_floor(i).set_waiting_count(0)


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
        print("misc_loop finished")


class AsyncMQTT:

    client: mqtt.Client

    def __init__(self, loop, dashboard: Dashboard):
        self.loop = loop
        self.dashboard = dashboard

        self.disconnected = self.loop.create_future()
        self.got_message = None

        self.client = mqtt.Client(client_id="dashboard")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.client.message_callback_add(f"simulation/reset", self.on_simulation_reset)
        self.client.message_callback_add(
            f"floor/+/arrived_passenger", self.on_arrived_passenger
        )
        self.client.message_callback_add(f"elevator/+/status", self.on_elevator_status)
        self.client.message_callback_add(f"elevator/+/queue", self.on_queue_update)
        self.client.message_callback_add(
            f"elevator/+/passengerEnter", self.on_passenger_enter
        )
        self.client.message_callback_add(
            f"simulation/config/passengerList/floor/+", self.on_new_passengers
        )

        aioh = AsyncioHelper(self.loop, self.client)

        self.client.connect("localhost", 1883)
        self.client.socket().setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2048)

    def on_connect(self, client, userdata, flags, rc):
        client.subscribe("#")

    def on_arrived_passenger(self, client, userdata, msg):
        floor_level = int(msg.topic.split("/")[1])
        payload = json.loads(msg.payload)

        self.dashboard.set_total_wait_time(floor_level, payload["total_wait_time"])

    def on_elevator_status(self, client, userdata, msg):
        id = int(msg.topic.split("/")[1])
        payload: dict = json.loads(msg.payload)

        elevator: Elevator = self.dashboard.get_elevator(id)
        state = str(payload["state"])
        capacity = int(payload["current_capacity"])
        position = int(payload["current_position"])

        elevator.set_statebox_text(state=state, capacity=capacity)
        elevator.set_position(position)

    def on_queue_update(self, client, userdata, msg):
        id = int(msg.topic.split("/")[1])
        queue_list: str = str(json.loads(msg.payload))

        self.dashboard.set_queue(id, queue_list)

    def on_new_passengers(self, client, userdata, msg):
        level = int(msg.topic.split("/")[4])
        passenger_list: dict = json.loads(msg.payload)

        floor: Floor = self.dashboard.get_floor(level)
        floor.set_waiting_count(floor.get_waiting_count() + len(passenger_list))

    def on_passenger_enter(self, client, userdata, msg):
        payload: dict = json.loads(msg.payload)
        level = payload["floor"]
        enter_count = len(payload["enter_list"])

        floor: Floor = self.dashboard.get_floor(level)
        floor.set_waiting_count(floor.get_waiting_count() - enter_count)

        id = int(msg.topic.split("/")[1])
        elevator: Elevator = self.dashboard.get_elevator(id)
        capacity = elevator.get_capacity() + enter_count
        elevator.set_statebox_text(state="ENTER", capacity=capacity)

    def on_simulation_reset(self, client, userdata, msg):
        # message are ignored
        self.dashboard.reset()

    def on_message(self, client, userdata, msg):
        # print("HHLLOO")
        pass

    def on_disconnect(self, client, userdata, rc):
        self.disconnected.set_result(rc)


async def main(loop):
    dashboard = Dashboard()
    dashboard.urwid_loop.start()

    mqtt = AsyncMQTT(loop, dashboard)
    # workaround so that this will never end
    await loop.create_future()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
