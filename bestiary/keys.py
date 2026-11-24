"""Single key presses for the battle UI: the arrows, Enter and Esc.

`read_key()` returns one of "up", "down", "left", "right", "enter", "space", "esc", "tab", "backtab", a lower-case
letter, or "" for a key the game ignores. It works on a Linux terminal (the console pod, through `kubectl exec -it`)
and on Windows (a local laptop). Ctrl-C still stops the game. While a menu is open the terminal stays in "cbreak"
mode (`raw_mode()`): keys that arrive in a burst are not echoed on the screen and none is lost between two reads; it
is restored afterwards.

Terminals do not agree on what an arrow sends, so the decoder knows the usual families: ESC [ A, ESC O A (application
mode), ESC [ 1 ; 5 A (with Ctrl or Shift), and the Windows Terminal "win32-input-mode" (ESC [ Vk ; Sc ; Uc ; Kd ; Cs ; Rc _).
When something arrives that is not recognised, `unknown` holds it so the screen can show it, and `bestiary keytest`
prints every key press with its raw bytes.
"""

from __future__ import annotations

import contextlib
import os
import sys

_ARROWS = {"A": "up", "B": "down", "C": "right", "D": "left"}   # ESC [ A, or ESC O A in "application" mode
_WINDOWS_ARROWS = {"H": "up", "P": "down", "K": "left", "M": "right"}
_VIRTUAL_KEYS = {38: "up", 40: "down", 37: "left", 39: "right", 13: "enter", 27: "esc", 32: "space", 9: "tab"}   # win32-input-mode
_saved_mode = None   # the terminal settings to restore, while raw_mode() is active
ESC_WAIT = 0.25      # seconds to wait for the rest of an escape sequence (a slow link may split it)

last_raw = ""        # the raw bytes of the last key, for display
unknown = ""         # the last escape sequence nobody recognised ("" once a known key arrives)


def stdin_is_tty() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def decode_escape(seq: str) -> str:
    """What the characters that follow ESC mean. '' (nothing followed) is the Esc key itself."""
    if not seq:
        return "esc"
    if seq == "[Z":
        return "backtab"
    if seq[0] in "[O" and seq[-1] in _ARROWS and not seq.endswith("_"):   # also ESC [ 1 ; 5 C (Ctrl+Right)
        return _ARROWS[seq[-1]]
    if seq[0] == "[" and seq.endswith("_"):   # win32-input-mode: ESC [ Vk ; Sc ; Uc ; Kd ; Cs ; Rc _  (Kd = 1 on key down)
        parts = (seq[1:-1].split(";") + ["0"] * 6)[:6]
        try:
            vk, uc, down = int(parts[0] or 0), int(parts[2] or 0), parts[3] == "1"
        except ValueError:
            return ""
        if not down:
            return ""
        if vk in _VIRTUAL_KEYS:
            return _VIRTUAL_KEYS[vk]
        return decode_char(chr(uc)) if 0 < uc < 128 else ""
    return ""


def read_escape(next_char) -> str:
    """The characters that follow ESC. `next_char()` returns the next one, or None if none arrives in time.

    ESC [ ... ends at the first character from @ to ~ (so ESC [ 1 ; 5 A and ESC [ 38 ; ... _ are read whole), and
    ESC O takes exactly one more (ESC O A). Anything else is Alt + a key: one character.
    """
    first = next_char()
    if first is None:
        return ""
    seq = first
    if first == "[":
        while (c := next_char()) is not None:
            seq += c
            if "@" <= c <= "~":
                break
    elif first == "O":
        c = next_char()
        if c is not None:
            seq += c
    return seq


def decode_char(ch: str) -> str:
    if ch in ("\r", "\n"):
        return "enter"
    if ch == " ":
        return "space"
    if ch == "\t":
        return "tab"
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

    global last_raw
    ch = msvcrt.getwch()
    last_raw = repr(ch)
    if ch in ("\x00", "\xe0"):
        second = msvcrt.getwch()
        last_raw += repr(second)
        return _WINDOWS_ARROWS.get(second, "")
    if ch == "\x1b":
        return "esc"
    return decode_char(ch)


def _read_posix() -> str:  # pragma: no cover - needs a terminal (covered by the pty check on the host)
    import select
    import termios
    import tty

    global last_raw, unknown
    fd = sys.stdin.fileno()
    old = None if _saved_mode is not None else termios.tcgetattr(fd)   # inside raw_mode() the mode is already set
    try:
        if old is not None:
            tty.setcbreak(fd)
        ch = os.read(fd, 1).decode("latin-1")
        last_raw = repr(ch)
        if ch != "\x1b":
            return decode_char(ch)

        def next_char():   # the rest of an arrow arrives within a few ms, or later on a slow link
            return os.read(fd, 1).decode("latin-1") if select.select([fd], [], [], ESC_WAIT)[0] else None

        seq = read_escape(next_char)
        last_raw = repr("\x1b" + seq)
        key = decode_escape(seq)
        unknown = "" if key or not seq else "ESC " + " ".join(seq)
        return key
    finally:
        if old is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def read_key() -> str:
    return _read_windows() if os.name == "nt" else _read_posix()
