"""Chat block: a team messenger with channels, direct messages, a message thread and a composer."""

import pyzed as pz
from pyzed import ui

CHANNELS = [("general", 0), ("design", 3), ("engineering", 12), ("releases", 0), ("random", 1)]
PEOPLE = [("Maya López", "online"), ("Jackson Lee", "online"), ("Isabella Nguyen", "away"), ("William Kim", "offline")]
PRESENCE = {"online": "success", "away": "warning", "offline": "text_disabled"}

MESSAGES = [
    ("Maya López", "09:12", "Morning! The new onboarding flow is on staging. Can someone give it a spin?", None),
    ("Jackson Lee", "09:14", "On it. First impression: **much** faster than the old one.", None),
    ("Jackson Lee", "09:15", "One nit: the progress bar jumps from step 2 to 4 when you skip the team invite.", None),
    ("Isabella Nguyen", "09:21", "Here's the build size before and after the switch to Pyzed:",
     ("build-report.pdf", "2.4 MB")),
    ("Maya López", "09:24", "Good catch, I'll fix the skip logic. Shipping it with `v2.3.1` this afternoon.", None),
]


def initials(name):
    return "".join(part[0] for part in name.split())


class Chat(pz.App):
    title = "Messages"
    size = (1200, 760)

    def __init__(self):
        self.channel = "design"
        self.draft = "Looks great! Let's demo it in Friday's review"
        self.messages = list(MESSAGES)
        self.reactions = {2: {"👍": 3, "🎯": 1}, 4: {"🚀": 4}}

    def send(self):
        if self.draft.strip():
            self.messages.append(("Kevin Vargas", "09:30", self.draft.strip(), None))
            self.draft = ""
        return pz.Command.scroll_to_end("chat-thread")

    # -- sidebar ---------------------------------------------------------------------------
    def sidebar(self):
        channels = [ui.list_item(f"# {name}", lambda name=name: setattr(self, "channel", name),
                                 selected=name == self.channel, height=30,
                                 end=ui.count_badge(unread) if unread else None)
                    for name, unread in CHANNELS]
        people = [ui.list_item(name, None, height=30, start=pz.stack([
                      ui.avatar(initials(name), size=20, index=i),
                      pz.container(ui.indicator(PRESENCE[status], size=7), width=22, height=22, align_x="end",
                                   align_y="end")]))
                  for i, (name, status) in enumerate(PEOPLE)]
        return pz.column([
            pz.row([ui.label("Acme", size="lg", weight="semibold"), pz.hspace(),
                    ui.icon_button("square-pen", None, tooltip="New message")], align="center"),
            ui.search_input("", None, placeholder="Jump to…"),
            pz.column([ui.list_header("Channels", end=ui.icon_button("plus", None, size="sm")), *channels],
                      spacing=2),
            pz.column([ui.list_header("Direct messages"), *people], spacing=2),
        ], spacing=16, width=250, height="fill", padding=(16, 12)).style(background="panel")

    # -- thread ----------------------------------------------------------------------------
    def message(self, index, author, time, text, attachment):
        previous = self.messages[index - 1][0] if index else None
        body = [ui.markdown(text)]
        if attachment:
            name, size = attachment
            body.append(pz.row([
                pz.container(pz.icon("file-text", size=18, color="#ffffff"), padding=8).style(
                    background="error", radius=8),
                pz.column([ui.label(name, weight="medium"), ui.muted(f"PDF · {size}", size="sm")], spacing=1),
                pz.hspace(width=24),
                ui.icon_button("download", None, tooltip="Download"),
            ], spacing=10, align="center").style(background="surface", border=(1, "border_variant"), radius=10,
                                                 padding=10, width="shrink"))
        reactions = self.reactions.get(index)
        if reactions:
            body.append(pz.row([ui.chip(f"{emoji} {count}", on_press=None) for emoji, count in reactions.items()],
                               spacing=6))
        if author == previous:  # a follow-up message: no avatar or name
            return pz.row([pz.space(width=36), pz.column(body, spacing=6, width="fill")], spacing=12,
                          padding=(2, 20))
        names = [a for a, _ in PEOPLE]
        header = pz.row([ui.label(author, weight="semibold"), ui.muted(time, size="sm")], spacing=8, align="end")
        return pz.row([
            ui.avatar(initials(author), size=36, index=names.index(author) if author in names else 5),
            pz.column([header, *body], spacing=6, width="fill"),
        ], spacing=12, padding=(10, 20, 2, 20))

    def composer(self):
        return pz.container(
            pz.column([
                ui.input(self.draft, lambda v: setattr(self, "draft", v), placeholder=f"Message #{self.channel}",
                         on_submit=self.send, borderless=True, id="composer"),
                pz.row([
                    ui.icon_button("plus", None, tooltip="Attach"),
                    ui.icon_button("bold", None), ui.icon_button("italic", None), ui.icon_button("code", None),
                    ui.icon_button("smile", None, tooltip="Emoji"),
                    ui.icon_button("at-sign", None, tooltip="Mention"),
                    pz.hspace(),
                    ui.muted("Enter to send", size="sm"),
                    ui.icon_button("send-horizontal", self.send, variant="solid" if self.draft else "ghost",
                                   tooltip="Send"),
                ], spacing=2, align="center"),
            ], spacing=6),
            padding=10, width="fill",
        ).style(background="surface", border=(1, "border"), radius=12)

    def view(self):
        header = pz.row([
            ui.label(f"# {self.channel}", size="lg", weight="semibold"),
            ui.muted("Product design, reviews and handoff", size="sm"),
            pz.hspace(),
            ui.facepile(["ML", "JL", "IN", "WK", "KV", "SD", "AB"], size=24, max_shown=4),
            ui.icon_button("phone", None, tooltip="Call"),
            ui.icon_button("pin", None, tooltip="Pinned"),
            ui.icon_button("panel-right", None, tooltip="Details"),
        ], spacing=10, align="center", padding=(12, 20))
        divider = pz.row([ui.divider(), ui.badge("Today", tint="accent", variant="outline"), ui.divider()],
                         spacing=10, align="center", padding=(8, 20))
        thread = pz.scrollable(
            pz.column([divider, *[self.message(i, *m) for i, m in enumerate(self.messages)]], spacing=4),
            height="fill", id="chat-thread", anchor_bottom=True)
        main = pz.column([header, ui.divider(), thread, pz.container(self.composer(), padding=(8, 20, 20, 20))],
                         width="fill", height="fill").style(background="editor")
        return pz.row([self.sidebar(), ui.divider(vertical=True), main], height="fill")


if __name__ == "__main__":
    pz.run(Chat)
