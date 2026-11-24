"""Single key presses for the battle UI: the arrows, Enter and Esc.

`read_key()` returns one of "up", "down", "left", "right", "enter", "space", "esc", a lower-case letter, or ""
for a key the game ignores. It works on a Linux terminal (the console pod, through `kubectl exec -it`) and on
Windows (a local laptop). Ctrl-C still stops the game. While a menu is open the terminal stays in "cbreak" mode (`raw_mode()`): keys that
arrive in a burst are not echoed on the screen and none is lost between two reads; it is restored afterwards.
"""

from __future__ import annotations

import contextlib
import os
import sys

_ARROWS = {"A": "up", "B": "down", "C": "right", "D": "left"}   # ESC [ A, or ESC O A in "application" mode
_WINDOWS_ARROWS = {"H": "up", "P": "down", "K": "left", "M": "right"}
_saved_mode = None   # the terminal settings to restore, while raw_mode() is active


def stdin_is_tty() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def decode_escape(seq: str) -> str:
    """What the bytes that follow ESC mean. '' (nothing followed) is the Esc key itself."""
    if not seq:
        return "esc"
    if seq[0] in "[O" and seq[-1] in _ARROWS:   # also ESC [ 1 ; 5 C (Ctrl+Right)
        return _ARROWS[seq[-1]]
    return ""


def decode_char(ch: str) -> str:
    if ch in ("\r", "\n"):
        return "enter"
    if ch == " ":
        return "space"
    if ch == "\x03":
        raise KeyboardInterrupt
    if ch.isascii() and ch.isprintable():
        return ch.lower()
    return ""


@contextlib.contextmanager
def raw_mode():
    """Keep the terminal in cbreak mode (no echo, no line buffering, Ctrl-C still works) until the block ends."""
    global _saved_mode
    if os.name == "nt" or _saved_mode is not None:
        yield
        return
    try:
        import termios
        import tty

        fd = sys.stdin.fileno()
        _saved_mode = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    except Exception:   # not a terminal (a pipe, a test): read_key then falls back to one key at a time
        _saved_mode = None
        yield
        return
    try:
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, _saved_mode)
        _saved_mode = None


def flush_input() -> None:
    """Drop keys pressed earlier (a double Enter must not choose for the presenter)."""
    try:
        if os.name == "nt":
            import msvcrt

            while msvcrt.kbhit():
                msvcrt.getwch()
        else:
            import termios

            termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except Exception:  # pragma: no cover - not a terminal
        pass


def _read_windows() -> str:  # pragma: no cover - needs a Windows console
    import msvcrt

    ch = msvcrt.getwch()
    if ch in ("\x00", "\xe0"):
        return _WINDOWS_ARROWS.get(msvcrt.getwch(), "")
    if ch == "\x1b":
        return "esc"
    return decode_char(ch)


def _read_posix() -> str:  # pragma: no cover - needs a terminal (covered by the pty check on the host)
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = None if _saved_mode is not None else termios.tcgetattr(fd)   # inside raw_mode() the mode is already set
    try:
        if old is not None:
            tty.setcbreak(fd)
        ch = os.read(fd, 1).decode("latin-1")
        if ch != "\x1b":
            return decode_char(ch)
        seq = ""
        while select.select([fd], [], [], 0.05)[0]:   # the rest of an arrow arrives within a few ms
            seq += os.read(fd, 1).decode("latin-1")
            if seq[-1].isalpha() or seq[-1] == "~":
                break
        return decode_escape(seq)
    finally:
        if old is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def read_key() -> str:
    return _read_windows() if os.name == "nt" else _read_posix()
