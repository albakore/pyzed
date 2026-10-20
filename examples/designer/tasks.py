"""Event handlers for the task runner: the non-visual components at work.

ticker (Timer) keeps the clock, proc (Process) runs the command and streams its output,
primes (Background worker) counts in a thread while the window stays responsive, notes (File
watcher) reports .txt files that change, prefs (Settings) remembers the command between runs,
run_key (Shortcut) runs it with Ctrl+R (Cmd+R on macOS) and toast (Notification) says when
the count is done.
"""

import time


def form_load(form, event):
    """Runs once when tasks opens."""
    form.status.text = "Press Run (or Ctrl+R), or count primes in the background."
    return form.command.focus()


def ticker_tick(form, event):
    """Runs every ``interval`` milliseconds while ticker is running."""
    form.clock.text = time.strftime("%H:%M:%S")


def run_click(form, event):
    """Runs when run is clicked."""
    if form.proc.running:
        form.proc.kill()
        return
    form.output.text = ""
    if form.proc.start(form.command.text):
        form.run.text = "Stop"
        form.status.text = f"Running {form.command.text}"


def command_submit(form, event):
    """Runs when Enter is pressed in command."""
    return run_click(form, event)


def run_key_activate(form, event):
    """Runs when the keys of run_key are pressed anywhere in the window."""
    return run_click(form, event)


def proc_output(form, event):
    """Runs for every line the program of proc prints."""
    form.output.text += event.value + "\n"


def proc_finished(form, event):
    """Runs when the program of proc ends (``event.value`` is its exit code)."""
    form.run.text = "Run"
    form.status.text = "Done." if event.value == 0 else f"It ended with code {event.value}."


def proc_failed(form, event):
    """Runs when the program of proc cannot start."""
    form.run.text = "Run"
    form.status.text = f"Could not run it: {event.value}"


def count_click(form, event):
    """Runs when count is clicked."""
    if form.primes.busy:
        form.primes.cancel()
    elif form.primes.run(200_000):
        form.count.text = "Cancel"


def primes_work(form, event):
    """Runs in a background thread when ``form.primes.run(value)`` is called; returns the result."""
    limit, found = event.value, 0
    for n in range(2, limit):
        if event.sender.cancelled:
            return None
        if all(n % d for d in range(2, int(n ** 0.5) + 1)):
            found += 1
        if n % 2000 == 0:
            event.sender.report(n * 100 // limit)
    return found


def primes_progress(form, event):
    """Runs when the work calls ``event.sender.report(value)``."""
    form.progress.value = event.value


def primes_done(form, event):
    """Runs when the work of primes ends (``event.value`` is what it returned)."""
    form.count.text = "Count primes"
    if event.value is None:
        form.status.text = "Cancelled."
        return
    form.progress.value = 100
    form.status.text = f"{event.value:,} primes below 200,000."
    form.toast.show(form.status.text)


def notes_change(form, event):
    """Runs after notes finds changes (``event.value`` lists the changed paths)."""
    names = ", ".join(path.rsplit("/", 1)[-1] for path in event.value)
    form.status.text = f"Changed: {names}"
