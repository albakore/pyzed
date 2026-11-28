"""Global state: values every page shares. Components that read them draw again when they change."""

import pyzed as pz


class Favorites(pz.Store):
    persist = "{name}-favorites"  # kept between runs
    ids: list = []

    def add(self, item_id):
        if item_id not in self.ids:
            self.ids = [*self.ids, item_id]


favorites = Favorites()
