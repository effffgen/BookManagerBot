from enum import IntEnum, auto


class OrderedEnum(IntEnum):
    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
           return self.value <= other.value
        return NotImplemented

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


class State(IntEnum):
    STATE_START = auto()
    STATE_ADDING = auto()
    STATE_TITLE = auto()
    STATE_DESCRIPTION = auto()
    STATE_AUTHORS = auto()
    STATE_COVER = auto()
    STATE_TAGS = auto()
    STATE_COMPLETE = auto()


for state in State:
    print(repr(state))