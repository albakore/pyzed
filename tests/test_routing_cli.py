"""``pyzed route add`` and ``pyzed route list``: route files from the command line."""

from __future__ import annotations

from pyzed import cli, component
from pyzed.routing import Router, scaffold


class Owner:
    """Stands for the window the router draws in."""


def test_route_add_writes_files_that_run(tmp_path, capsys):
    app = tmp_path / "app"
    assert cli.main(["route", "add", "/", "--layout", "--not-found", "--error", "--app", str(app)]) == 0
    assert cli.main(["route", "add", "/products/[id]", "--load", "--loading", "--app", str(app)]) == 0
    assert cli.main(["route", "add", "/docs/[...slug]", "--load", "sync", "--app", str(app)]) == 0
    assert cli.main(["route", "add", "/(shop)/cart", "--middleware", "--template", "--app", str(app)]) == 0
    out = capsys.readouterr().out.replace("\\", "/")
    assert "created" in out and "products/[id]/page.py" in out
    router = Router(app)
    assert router.routes() == ["/", "/cart", "/docs/[...slug]", "/products/[id]"]
    owner = Owner()
    for url in ("/", "/products/3", "/docs/a/b", "/cart", "/nothing"):
        router.push(url)
        with component.render_pass(owner):
            router.view()
        assert router.wait(5)
        with component.render_pass(owner):
            router.view()
    cart = scaffold.source_for("middleware", "/(shop)/cart")
    assert 'matcher = ["/cart/:path*"]' in cart


def test_route_add_keeps_files_and_refuses_bad_names(tmp_path, capsys):
    app = tmp_path / "app"
    assert cli.main(["route", "add", "/a", "--app", str(app)]) == 0
    (app / "a" / "page.py").write_text("def page():\n    return 'mine'\n")
    assert cli.main(["route", "add", "/a", "--app", str(app)]) == 0
    assert "mine" in (app / "a" / "page.py").read_text()
    assert "kept 1" in capsys.readouterr().out
    assert cli.main(["route", "add", "/_private", "--app", str(app)]) == 1
    assert cli.main(["route", "add", "/[a-b]", "--app", str(app)]) == 1
    assert cli.main(["route", "add", "/x", "--no-page", "--app", str(app)]) == 1


def test_route_list(tmp_path, capsys):
    app = tmp_path / "app"
    assert cli.main(["route", "list", "--app", str(app)]) == 1
    scaffold.add("/", ["page", "layout"], app=app)
    scaffold.add("/users/[id]", ["page", "loading"], app=app)
    capsys.readouterr()
    assert cli.main(["route", "list", "--app", str(app)]) == 0
    out = capsys.readouterr().out
    assert "/users/[id]" in out and "λ dynamic" in out and "○ static" in out and "loading" in out
