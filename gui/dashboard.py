# dashboard.py

import asyncio

import urwid

from components import (  # pylint: disable=import-error
    FLOOR_COUNT,
    FLOOR_OFFSET,
    ElevatorUI,
    FloorUI,
)

ELEVATOR_COUNT = 6

STATUS_HEIGHT = FLOOR_OFFSET * FLOOR_COUNT + 3
STATISTICS_HEIGHT = 3

TEXTBOX_WIDTH = 8
ELEVATOR_WIDTH = TEXTBOX_WIDTH + 2

UPDATE_PERIOD = 0.1


class DashboardUI:

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
            floors.append((floor_height, FloorUI(i)))
            floors.append(("fixed", 1, hline))

        self.floors = urwid.Pile(floors)
        floors = urwid.Filler(self.floors, "top")

        elevators = []
        for i in range(0, ELEVATOR_COUNT):
            elevators.append(("fixed", ELEVATOR_WIDTH, ElevatorUI(id=i)))
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
            idx_in_section = int(floor)
        else:
            section = self.wait_time_values.contents[1][0]
            idx_in_section = int(floor - FLOOR_COUNT / 2)

        # access time in the section
        return section.contents[idx_in_section][0]

    def set_total_wait_time(self, floor: int, time: str):
        self.get_wait_time(int(floor)).set_text(f"Floor {floor}: {time}")

    def get_queue(self, id: int) -> urwid.Text:
        # skip the header and divider '-'
        return self.queue.contents[2 + id][0]

    def set_queue(self, id: int, queue: str):
        self.get_queue(id).set_text(f"E{id}: {queue}")

    def get_elevator(self, idx: int) -> ElevatorUI:
        return self.elevators.contents[idx][0]

    def get_floor(self, floor: int) -> FloorUI:
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


async def main(loop):
    from async_mqtt import AsyncMQTT  # pylint: disable=import-error

    dashboard = DashboardUI()
    dashboard.urwid_loop.start()

    AsyncMQTT(loop, dashboard)
    # workaround so that this will never end
    await loop.create_future()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
