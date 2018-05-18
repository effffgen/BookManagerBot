from enum import IntEnum, auto


class State(IntEnum):
    STATE_START = auto()
    STATE_USERLANG = auto()
    STATE_FIND = auto()
    STATE_TITLE = auto()
    STATE_DESCRIPTION = auto()
    STATE_AUTHORS = auto()
    STATE_COVER = auto()
    STATE_LANG = auto()
    STATE_TAGS = auto()
    STATE_COMPLETE = auto()


"""
for state in State:
    print(repr(state))
"""