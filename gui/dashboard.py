# dashboard.py


from datetime import datetime, timedelta

import argparse
import os
import signal
import threading
import urwid

from components import (  # pylint: disable=import-error
    FLOOR_COUNT,
    FLOOR_OFFSET,
    ElevatorUI,
    FloorUI,
)

ELEVATOR_COUNT = 6

STATUS_HEIGHT = FLOOR_OFFSET * FLOOR_COUNT + 3
STATISTICS_HEIGHT = 9

TEXTBOX_WIDTH = 10
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

    urwid_loop: urwid.MainLoop

    def __init__(self):
        self.frame = self.build_dashboard()

        self.urwid_loop: urwid.MainLoop = urwid.MainLoop(
            self.frame, self.palette,
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

        # FLOORS

        floor_height = 1
        floors = []
        floors.append(("fixed", 1, hline))
        for i in range(FLOOR_COUNT - 1, -1, -1):
            floors.append((floor_height, FloorUI(i)))
            floors.append(("fixed", 1, hline))

        self.floors = urwid.Pile(floors)
        floors = urwid.Filler(self.floors, "top")

        # ELEVATOR

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

        # PASSENGER COUNT

        self.total_expected = 0
        self.total_arrived = 0
        self.passenger_count = [
            {"floor": i, "arrived": 0, "expected": 0} for i in range(0, FLOOR_COUNT)
        ]

        arrived_elements = [
            urwid.Text(
                f"Floor {c['floor']}: {c['arrived']}/{c['expected']}", align="center"
            )
            for c in self.passenger_count
        ]
        idx_middle = int(len(arrived_elements) / 2)
        arrived_left = urwid.Pile(arrived_elements[:idx_middle])
        arrived_right = urwid.Pile(arrived_elements[idx_middle:])
        self.arrived_values = urwid.Columns([arrived_left, arrived_right])

        sum_expected = 0
        sum_arrived = 0
        self.arrived_total: urwid.Text = urwid.Text(
            f"Total: {sum_arrived}/{sum_expected}", align="center"
        )

        arrived = urwid.Pile(
            [self.arrived_values, urwid.Divider("-"), self.arrived_total]
        )
        arrived = urwid.LineBox(arrived, title="Passenger Count (arrived/expected)")

        # WAIT TIME

        # self.wait_time_widgets = [
        #     urwid.Text(f"Floor {f}: 0:00:00.000000", align="center")
        #     for f in range(0, FLOOR_COUNT)
        # ]

        # # separate the times to two sections left and right to save vertical space
        # idx_middle = int(len(self.wait_time_widgets) / 2)
        # wait_time_left = urwid.Pile(self.wait_time_widgets[:idx_middle])
        # wait_time_right = urwid.Pile(self.wait_time_widgets[idx_middle:])
        # wait_time_middle = urwid.Columns([wait_time_left, wait_time_right])

        # # this holds the real total value
        # self.total_wait_time = None
        # # this holds the urwid widget for UI
        # self.total_wait_time_widget = urwid.Text(
        #     f"Total: 0:00:00.000000 | Average: 0:00:00.000000", align="center",
        # )
        # wait_time = urwid.Pile(
        #     [wait_time_middle, urwid.Divider("-"), self.total_wait_time_widget]
        # )
        # wait_time._selectable = False
        # wait_time = urwid.Padding(wait_time, right=1)
        # wait_time = urwid.LineBox(wait_time, title="Waiting Time")

        # QUEUE

        queue_elements = [
            urwid.Text(f"E{i}: []", wrap="ellipsis") for i in range(0, ELEVATOR_COUNT)
        ]
        self.queue = urwid.Pile(queue_elements)
        self.queue._selectable = False
        queue_box = self.queue
        queue_box = urwid.Padding(queue_box, left=1)
        queue_box = urwid.Filler(queue_box, valign="middle")
        queue_box = urwid.LineBox(queue_box, title="Elevator Destination Queue")

        # TOP, BOTTOM

        statistics = urwid.Columns(
            [
                arrived,
                # wait_time,
                urwid.BoxAdapter(queue_box, STATISTICS_HEIGHT),
            ]
        )
        statistics = urwid.Filler(statistics)

        # FIXME: replace len(arrived_elements) with more general height
        return urwid.Pile([(STATISTICS_HEIGHT, statistics), (STATUS_HEIGHT, status)])

    def get_passenger_count_entry(self, floor: int) -> urwid.Text:
        # left or right
        if floor < FLOOR_COUNT / 2:
            section = self.arrived_values.contents[0][0]
            idx_in_section = int(floor)
        else:
            section = self.arrived_values.contents[1][0]
            idx_in_section = int(floor - FLOOR_COUNT / 2)

        # access time in the section
        return section.contents[idx_in_section][0]

    def set_passenger_count_entry(
        self, floor: int, arrived: int = None, expected: int = None
    ):
        c = self.passenger_count[floor]
        if arrived is not None:
            c["arrived"] = arrived
        if expected is not None:
            c["expected"] = expected
        self.get_passenger_count_entry(floor).set_text(
            f"Floor {floor}: {c['arrived']}/{c['expected']}"
        )

        self.update_total_passenger_count()

    def update_total_passenger_count(self):
        arrived = 0
        expected = 0
        for c in self.passenger_count:
            arrived += int(c["arrived"])
            expected += int(c["expected"])
        self.total_arrived = arrived
        self.total_expected = expected
        self.arrived_total.set_text(
            f"Total: {self.total_arrived}/{self.total_expected}"
        )

    # def get_wait_time(self, floor: int) -> urwid.Text:
    #     return self.wait_time_widgets[floor]

    # def set_wait_time(self, floor: int, wait_time: str):
    #     # update floor wait time
    #     self.get_wait_time(floor).set_text(f"Floor {floor}: {wait_time}")
    #     # update total wait time
    #     new_time = datetime.strptime(wait_time, "%H:%M:%S.%f")
    #     new_time = timedelta(
    #         hours=new_time.hour,
    #         minutes=new_time.minute,
    #         seconds=new_time.second,
    #         microseconds=new_time.microsecond,
    #     )

    #     if self.total_wait_time is None:
    #         self.total_wait_time = new_time
    #     else:
    #         self.total_wait_time = self.total_wait_time + new_time

    #     if self.total_arrived <= 0:
    #         # workaround: skip if still zero
    #         return

    #     # convert to microseconds first for easier calculation
    #     average = (
    #         self.total_wait_time / timedelta(microseconds=1)
    #     ) / self.total_arrived
    #     average = timedelta(microseconds=average)
    #     self.total_wait_time_widget.set_text(
    #         f"Total: {str(self.total_wait_time)} | Average {str(average)}"
    #     )

    def get_queue(self, id: int) -> urwid.Text:
        # skip the header and divider '-'
        return self.queue.contents[id][0]

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
            self.get_elevator(i).set_floor(0)
            self.get_elevator(i).set_statebox_text(state="OPEN", capacity=0)
        for i in range(0, FLOOR_COUNT):
            self.get_floor(i).set_waiting_count(0)


def signal_handler(signal, frame):
    raise urwid.ExitMainLoop()


def main(host: str = "localhost"):
    signal.signal(signal.SIGINT, signal_handler)

    from async_mqtt import MQTTclient  # pylint: disable=import-error

    dashboard = DashboardUI()

    mqtt_client = MQTTclient(dashboard=dashboard, host=host)
    mqtt_thread = threading.Thread(target=mqtt_client.run)
    mqtt_thread.start()

    dashboard.urwid_loop.run()
    mqtt_client.do_run = False
    mqtt_thread.join()


if __name__ == "__main__":
    argp = argparse.ArgumentParser(description="simulator for mqtt messages")
    argp.add_argument(
        "-host",
        action="store",
        dest="host",
        default="localhost",
        help="default: localhost",
    )
    args = argp.parse_args()
    host = os.getenv("mqtt_host", args.host)

    main(host)
