"""Tutorial, step 1: a window with some text.

    python examples/tutorial/step1_hello.py
"""

import pyzed as pz


class Hello(pz.App):
    title = "Hello"
    size = (400, 200)

    def view(self):
        # view() returns a tree of widgets; Pyzed calls it again after every change.
        return pz.center(pz.text("Hello, Pyzed!", size=28))


if __name__ == "__main__":
    pz.run(Hello)
