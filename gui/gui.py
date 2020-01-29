import os
import urwid


FLOOR_OFFSET = 2
FLOOR_COUNT = 10
ELEVATOR_COUNT = 5


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
    width: int
    status: str
    top_offset: int
    bottom_offset: int

    def __init__(self, id: str, text="default", position: int = 0):
        self.top_offset = FLOOR_OFFSET * (FLOOR_COUNT - position - 1)
        self.bottom_offset = FLOOR_OFFSET * position

        textbox = urwid.Text(self.make_textbox(text), align="center")
        textbox = urwid.Filler(textbox, top=self.top_offset, bottom=self.bottom_offset)

        title = urwid.Filler(urwid.Text(id, align="center"))

        self.status = "DRIVING"
        status = urwid.Filler(urwid.Text(self.status, align="center"))

        elements = [
            (1, title),
            urwid.Divider("-"),
            (1, status),
            urwid.Divider("-"),
            (3 + self.top_offset + self.bottom_offset, textbox),
        ]
        w = urwid.Pile(elements)
        w._selectable = False
        super().__init__(w)

    def make_textbox(self, text: str):
        upper_border = "\u250C" + ("\u2500" * len(text)) + "\u2510\n"
        bottom_border = "\u2514" + ("\u2500" * len(text)) + "\u2518"
        middle = "\u2502" + text + "\u2502\n"

        self.width = len(middle)
        return upper_border + middle + bottom_border

    def get_width(self):
        return self.width

    def update_text(self, text: str):
        pass

    def update_status(self, status: str):
        self.status = status


class Simulation(object):

    palette = [
        # ("body", "dark cyan", "", "standout"),
        # ("focus", "dark red", "", "standout"),
        # ("head", "light red", "black"),
        ("hline", "white", "", "white"),
        ("vline", "black", "light gray", "standout"),
    ]

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

    floors = urwid.Pile(floors)
    floors = urwid.Filler(floors, "bottom")

    elevators = []
    for i in range(0, ELEVATOR_COUNT):
        elevators.append(("fixed", 10, Elevator(id="A")))
    elevators = urwid.Columns(elevators)
    elevators = urwid.Filler(elevators, "bottom")

    status_content = urwid.Columns([floors, ("fixed", 1, vline), elevators])
    status = urwid.LineBox(status_content, title="Status")

    box = urwid.Frame(status)
    loop = urwid.MainLoop(box, palette)
    loop.run()


if __name__ == "__main__":
    Simulation()
