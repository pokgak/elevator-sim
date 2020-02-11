# components.py

import urwid

FLOOR_OFFSET = 2
FLOOR_COUNT = 10


class FloorUI(urwid.WidgetWrap):
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


class ElevatorUI(urwid.WidgetWrap):
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

    def set_floor(self, position: int):
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
