class NTRIPStatus:
    text: str
    value: int
    exception: Exception

    def __init__(self, text: str, value: int):
        self.text = text
        self.value = value

    def __eq__(self, other):
        if isinstance(other, NTRIPStatus):
            return other.value == self.value
        elif isinstance(other, int):
            return other == self.value
        return False
