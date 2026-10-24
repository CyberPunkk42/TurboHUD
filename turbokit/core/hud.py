"""What the HUD shows and where, as plain data that turbokit.hud draws."""

from dataclasses import dataclass

MARGIN = 14  # space between the box's edge and the text, before scaling


@dataclass(frozen=True)
class Line:
    text: str
    size: int  # font size in pixels
    color: str  # 'text' or 'accent', a colour from the theme
    baseline: int  # y of the text's baseline, from the box's top


def clock(seconds):
    """'m:ss' for a number of seconds, like a lap time."""
    minutes, seconds = divmod(int(seconds), 60)
    return f'{minutes}:{seconds:02d}'


def help_text(locked, shortcuts):
    """The hint shown in the HUD: none while locked, how to finish in move mode."""
    if locked:
        return ''
    if shortcuts:
        return 'Drag to move, resize at the corner. Ctrl+Shift+L locks.'
    return 'Drag to move, resize at the corner, then Lock.'


def hud_lines(seconds, locked, shortcuts, scale=1.0):
    """The HUD's lines, top to bottom."""

    def scaled(value):
        return round(value * scale)

    title, big, small = scaled(16), scaled(40), scaled(13)
    baseline = scaled(MARGIN) + title
    lines = [Line('TurboKit - session time', title, 'text', baseline)]
    baseline += scaled(8) + big
    lines.append(Line(clock(seconds), big, 'accent', baseline))
    hint = help_text(locked, shortcuts)
    if hint:
        baseline += scaled(10) + small
        lines.append(Line(hint, small, 'text', baseline))
    return lines
