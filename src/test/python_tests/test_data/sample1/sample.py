import sys

print(x)


class Foo:
    def __eq__(self, other: "Foo") -> bool:
        return True
