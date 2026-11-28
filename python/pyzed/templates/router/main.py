"""{name}: a Pyzed app with routes in folders, like Next.js. Run it with `python main.py`.

Every folder of app/ is a part of the URL: add app/contact/page.py and /contact exists, or run
`pyzed route add /contact`. `pyzed route list` shows every route.

api.py holds the calls to the server and state.py the global state the pages share.
"""

import pyzed as pz


class App(pz.RouterApp):
    routes = "app"
    title = "{name}"
    size = (1000, 680)


if __name__ == "__main__":
    pz.run(App)
