import struct


class Hash128:
    Value: str

    def __repr__(self):
        return self.Value

    def __init__(self, *values):
        self.Value = (
            values[0] if len(values) == 1 else struct.pack(">IIII", *values).hex()
        )


__all__ = ["Hash128"]
