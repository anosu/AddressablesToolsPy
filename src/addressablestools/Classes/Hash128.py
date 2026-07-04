import struct


class Hash128:
    __slots__ = ["Value"]

    Value: str

    def __eq__(self, value):
        return self.Value == value.Value

    def __repr__(self):
        return f"{self.__class__.__name__}(Value={self.Value})"

    def __init__(self, *values):
        self.Value = (
            values[0] if len(values) == 1 else struct.pack("<IIII", *values).hex()
        )


__all__ = ["Hash128"]
