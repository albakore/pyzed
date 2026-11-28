"""The app's global state: who is signed in and what is in the cart.

Every page and the layout read these; the components that read them draw again when they change.
"""

import pyzed as pz


class Session(pz.Store):
    user: dict = {}

    @property
    def signed_in(self):
        return bool(self.user)


class Cart(pz.Store):
    items: list = []  # product ids

    @property
    def count(self):
        return len(self.items)

    def add(self, product_id):
        self.items = [*self.items, product_id]


session = Session()
cart = Cart()
