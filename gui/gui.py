import os
import urwid
import asyncio


FLOOR_OFFSET = 2
FLOOR_COUNT = 5
ELEVATOR_COUNT = 5

TEXTBOX_WIDTH = 8
ELEVATOR_WIDTH = TEXTBOX_WIDTH + 2


class Floor(urwid.WidgetWrap):
    _sizing = frozenset(["box"])

    def __init__(
        self, floor: int, waiting_count: int = 0,
    ):
        self.floor = floor
        self._selectable = False

        elements = []
        # if self.floor != floor_max:
        #     elements.append(urwid.Divider("-"))
        elements.append(
            urwid.Padding(
                urwid.Text(
                    " 0" * waiting_count + f" [{floor}]", align="right", wrap="ellipsis"
                ),
                right=1,
            )
        )
        # if self.floor != 0:
        #     elements.append(urwid.Divider("-"))
        w = urwid.ListBox(urwid.SimpleListWalker(elements))
        super().__init__(w)


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

    def get_statebox(self):
        return self._w.base_widget

    def get_state(self):
        return self.get_statebox.get_text()

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


class Simulation(object):

    palette = [
        # ("body", "dark cyan", "", "standout"),
        # ("focus", "dark red", "", "standout"),
        # ("head", "light red", "black"),
        ("hline", "white", "", "white"),
        ("vline", "black", "light gray", "standout"),
    ]

    def __init__(self):
        frame = self.build_dashboard()

        self.asyncio_loop = asyncio.get_event_loop()
        self.urwid_loop = urwid.MainLoop(
            frame,
            self.palette,
            event_loop=urwid.AsyncioEventLoop(loop=self.asyncio_loop),
        )

        test = self.get_elevator(0)

        self.asyncio_loop.call_later(1, test.set_state, "UP")
        self.asyncio_loop.call_later(2, test.set_state, "DOWN")
        self.asyncio_loop.call_later(3, test.set_state, "ENTER")
        self.asyncio_loop.call_later(4, test.set_state, "EXIT")
        self.asyncio_loop.call_later(5, test.set_state, "IDLE")

        self.asyncio_loop.call_later(1, test.set_position, 1)
        self.asyncio_loop.call_later(2, test.set_position, 2)
        self.asyncio_loop.call_later(3, test.set_position, 3)
        self.asyncio_loop.call_later(4, test.set_position, 4)
        self.asyncio_loop.call_later(5, test.set_position, 0)

        self.urwid_loop.run()

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


if __name__ == "__main__":
    Simulation()
