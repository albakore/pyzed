"""The agent components of ``pyzed.ui`` (tool calls, plan, edits bar, history, sign-in, settings rows)."""

import time

from pyzed import ui
from pyzed.ui import agent


def test_tokens_and_the_context_meter():
    assert [ui.format_tokens(n) for n in (0, 950, 4_500, 48_000, 1_250_000)] == ["0", "950", "4.5k", "48k", "1.25M"]
    for used in (1_000, 170_000, 199_000):  # muted, warning, error
        ui.context_meter(used, 200_000)
    ui.context_meter(10, 0)


def test_history_groups_by_day_and_searches():
    now = time.time()
    assert agent.date_group(now, now) == "today"
    assert agent.date_group(now - 86400 * 1.01, now) in ("yesterday", "week")
    assert agent.date_group(now - 86400 * 400, now) == "older"
    got = []
    threads = [{"id": "1", "title": "Login form", "updated": now, "detail": "Opus 5.5"},
               {"id": "2", "title": "Notes app", "updated": now - 86400 * 40}]
    history = ui.ThreadHistory.create(threads=threads, on_open=lambda e: got.append(("open", e.value)),
                                      on_delete=lambda e: got.append(("delete", e.value)))
    history.render()
    history.set_query("opus")
    assert [t["id"] for t in history.visible()] == ["1"]
    history.set_query("nothing like it")
    history.render()  # "Nothing matches"
    history.emit("open", "1")
    history.emit("delete", "2")
    assert got == [("open", "1"), ("delete", "2")]


def test_tool_call_asks_on_the_card():
    got = []
    card = ui.ToolCall.create(title="Edit file", detail="ui/main.py", kind="edit", status="waiting",
                              input={"path": "ui/main.py"}, output="ok", on_allow=lambda e: got.append("allow"),
                              on_deny=lambda e: got.append("deny"))
    card.render()
    card.toggle()
    assert card.expanded
    card.render()
    card.emit("allow")
    card.emit("deny")
    assert got == ["allow", "deny"]
    for status in ("running", "done", "failed", "rejected"):
        ui.ToolCall.create(title="Read", status=status).render()


def test_plan_edits_bar_sign_in_rows_and_catalog():
    plan = ui.Plan.create(steps=[{"step": "a", "status": "done"}, {"step": "b", "status": "in_progress"}],
                          running=True)
    plan.render()
    plan.toggle()
    plan.render()
    got = []
    bar = ui.EditsBar.create(files=[{"path": "ui/main.py", "added": 3, "removed": 1}],
                             on_reject_file=lambda e: got.append(e.value))
    bar.toggle()
    bar.render()
    bar.emit("reject_file", "ui/main.py")
    assert got == ["ui/main.py"]
    prompt = ui.AuthPrompt.create(title="Sign in", methods=[{"id": "browser", "name": "Log in with the browser"}],
                                  on_pick=lambda e: got.append(e.value))
    prompt.render()
    prompt.emit("pick", "browser")
    ui.AuthPrompt.create(title="Sign in", waiting="browser", code="ABCD-1234", url="https://example.com").render()
    ran = []
    row = ui.ServiceRow.create(name="github", detail="npx server", status="error", status_text="exited",
                               enabled=True, actions=[ui.MenuItem("Restart", lambda: ran.append("restart"))])
    row.toggle_menu()
    row.render()
    row._run(lambda: ran.append("restart"))
    assert ran == ["restart"] and not row.menu_open
    catalog = ui.Catalog.create(items=[{"id": "gemini", "name": "Gemini CLI", "update": "0.65.0"},
                                       {"id": "codex", "name": "Codex", "installed": True}])
    catalog.set_query("gem")
    assert [i["id"] for i in catalog.visible()] == ["gemini"]
    catalog.render()
    assert got == ["ui/main.py", "browser"]


def test_a_long_diff_unfolds_from_its_more_lines_button_and_scrolls(monkeypatch):
    from ui_tree import install

    install(monkeypatch)
    old = "".join(f"line {i}\n" for i in range(60))
    new = "".join(f"line {i} changed a lot, so much that it is wider than the panel\n" for i in range(60))
    card = ui.ToolCall.create(title="Write", detail="README.md", kind="edit", status="done",
                              diffs=[{"path": "README.md", "old": old, "new": new}])
    tree = card.render()
    more = next(text for text in tree.texts() if "more lines" in text)
    tree.button_with(more).args[1]()  # it was a label that could not be pressed
    assert card.expanded
    tree = card.render()
    assert not any("more lines" in text for text in tree.texts())
    scroll = tree.find("scrollable")  # long lines scroll sideways, many lines scroll down
    assert scroll.props["height"] <= agent.DIFF_HEIGHT
    assert tree.find("scrollable", lambda n: n.props.get("direction") == "horizontal")
    tree.button_with("Show less").args[1]()
    assert not card.expanded


def test_a_long_command_is_cut_in_its_header_and_shown_whole_when_unfolded(monkeypatch):
    from ui_tree import install

    install(monkeypatch)
    command = 'cd "/c/Users/me/Pyzed Projects/discord-clone" && ' + "printf 'x' " * 40
    card = ui.ToolCall.create(title="Run", detail=command, kind="execute", status="done",
                              input={"command": command}, output="\n".join(f"out {i}" for i in range(40)))
    tree = card.render()
    header = tree.find("container", lambda n: n.props.get("clip") and command in n.texts())
    assert header.props["width"] == "fill"  # the header cuts it at the card's edge
    card.toggle()
    tree = card.render()
    whole = tree.find("text", lambda n: n.args[0] == "$ " + command)
    assert whole.props.get("selectable")  # it wraps and can be selected and copied
    assert tree.find("scrollable").props["height"] <= agent.OUTPUT_HEIGHT
