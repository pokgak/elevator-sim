import os
import urwid
import asyncio
import socket
import paho.mqtt.client as mqtt

FLOOR_OFFSET = 2
FLOOR_COUNT = 5
ELEVATOR_COUNT = 5

TEXTBOX_WIDTH = 8
ELEVATOR_WIDTH = TEXTBOX_WIDTH + 2


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
    id: str

    def __init__(self, id: str, text="IDLE", position: int = 0):
        self.position = position
        self.id = id

        statebox = urwid.Text(text, align="center")
        statebox = urwid.LineBox(statebox, title=id)
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

    def get_state(self) -> str:
        return self.get_statebox().get_text()[0]

    def set_state(self, text: str):
        self.get_statebox().set_text(text)

    def get_position(self) -> int:
        return self.position

    def set_position(self, position: int):
        self.position = position
        self._w = urwid.Filler(
            urwid.LineBox(self.get_statebox(), title=self.id),
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

        frame = self.build_dashboard()

        self.urwid_loop = urwid.MainLoop(
            frame,
            self.palette,
            event_loop=urwid.AsyncioEventLoop(loop=self.asyncio_loop),
        )

        e = self.get_elevator(0)

        self.asyncio_loop.call_later(1, e.set_state, "UP")
        self.asyncio_loop.call_later(2, e.set_state, "DOWN")
        self.asyncio_loop.call_later(3, e.set_state, "ENTER")
        self.asyncio_loop.call_later(4, e.set_state, "EXIT")
        self.asyncio_loop.call_later(5, e.set_state, "IDLE")

        self.asyncio_loop.call_later(1, e.set_position, 1)
        self.asyncio_loop.call_later(2, e.set_position, 2)
        self.asyncio_loop.call_later(3, e.set_position, 3)
        self.asyncio_loop.call_later(4, e.set_position, 4)
        self.asyncio_loop.call_later(5, e.set_position, 0)

        f = self.get_floor(3)
        print(f)

        self.asyncio_loop.call_later(3, f.set_waiting_count, f.get_waiting_count() + 10)

    def build_dashboard(self):
        # FIXME: replace by actual value
        import random

        random.seed()

        hline = urwid.AttrMap(urwid.SolidFill("\u2500"), "hline")
        vline = urwid.AttrMap(urwid.SolidFill("\u2502"), "vline")

        floor_height = 1
        floors = []
        floors.append(("fixed", 1, hline))
        for i in range(FLOOR_COUNT - 1, -1, -1):
            floors.append((floor_height, Floor(i, random.randint(0, 20))))
            floors.append(("fixed", 1, hline))

        self.floors = urwid.Pile(floors)
        floors = urwid.Filler(self.floors, "top")

        elevators = []
        for i in range(0, ELEVATOR_COUNT):
            elevators.append(("fixed", ELEVATOR_WIDTH, Elevator(id="A")))
        self.elevators = urwid.Columns(elevators, min_width=7)
        elevators = urwid.Filler(self.elevators, "top")

        status = urwid.Columns([floors, ("fixed", 1, vline), self.elevators])
        status = urwid.LineBox(status, title="Status")

        return status

    def get_elevator(self, idx: int) -> Elevator:
        return self.elevators.contents[idx][0]

    def get_floor(self, floor: int) -> Floor:
        return self.floors.contents[floor][0]


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

    def __init__(self, loop, dashboard):
        self.loop = loop
        self.dashboard = dashboard

    def on_connect(self, client, userdata, flags, rc):
        client.subscribe("test")

    def on_message(self, client, userdata, msg):
        print("HHLLOO")
        pass

    def on_disconnect(self, client, userdata, rc):
        self.disconnected.set_result(rc)

    async def start(self):
        self.disconnected = self.loop.create_future()
        self.got_message = None

        self.client = mqtt.Client(client_id="test")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        aioh = AsyncioHelper(self.loop, self.client)

        self.client.connect("localhost", 1883)
        self.client.socket().setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2048)

async def main(loop):
    dashboard = Dashboard()
    dashboard.urwid_loop.start()

    await AsyncMQTT(loop, dashboard).start()

    # workaround so that this will never end
    await loop.create_future()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
    # loop.create_task(main())
    # loop.run_forever()
    # loop.run_until_complete(main())
