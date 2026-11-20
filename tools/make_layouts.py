"""Make the shipped layouts and starting presets from the user's own (asked for by the user on
2026-11-20): one layout file made in move mode (Export..., customization/display_presets) becomes
assets/presets' layout for its screen size and, fitted with presets.fit_layout, for every other size
TurboHUD ships (presets.SCREENS); the presets in a settings file become assets/presets/starting
(presets.STARTING_FILE), which a first start fits to the player's screen. A layout designed by hand
for another size (the design screen's Save design...) is shipped as it is, instead of a fitted one.

    py -3 tools/make_layouts.py LAYOUT.json [--settings SETTINGS.json] [--designed SIZE.json ...]

(macOS, Linux: .buildtools/venv/bin/python.) The presets must have been saved on a screen of the
layout's size at the top left (0, 0), as the user's are. Only the places, sizes, options, names and
Load by itself choices are written: nothing personal. The files are written with CRLF, as the
shipped layouts always were.
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
if sys.platform == 'win32':  # offscreen finds no fonts there without this
    os.environ.setdefault('QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts'))

SHIPPED = ROOT / 'assets' / 'presets'


def write(path, data, how=''):
    """`data` as JSON with CRLF line endings, whole or not at all."""
    text = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(text.replace('\n', '\r\n').encode('utf-8'))
    temporary.replace(path)
    print(f'written: {path.relative_to(ROOT)}' + (f' ({how})' if how else ''))


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split('. ')[0])
    parser.add_argument('layout', help='the layout every size without a designed one is fitted from')
    parser.add_argument('--settings', help="the settings file whose presets become the starting presets")
    parser.add_argument(
        '--designed', nargs='*', default=[], help='layouts designed for other sizes, shipped as they are'
    )
    args = parser.parse_args(argv)
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])  # noqa: F841 (text is measured through Qt)
    from turbohud.core import presets
    from turbohud.core.hud import RACE_SECTIONS, common_font
    from turbohud.core.settings import load_settings
    from turbohud.hud.painter import text_ink, text_width

    sections = {section.name: section for section in RACE_SECTIONS}
    made = {}  # screen size -> places, as designed
    for path in [args.layout, *args.designed]:
        found = presets.load_file(path)
        if found is None:
            print(f'not a TurboHUD layout: {path}')
            return 1
        if tuple(found[0]) not in presets.SCREENS:
            print(f'{path}: {found[0][0]}x{found[0][1]} is not a size TurboHUD ships')
            return 1
        missing = set(sections) - set(found[1])
        if missing:
            print(f'{path}: without {", ".join(sorted(missing))} (made before those sections?)')
            return 1
        made[tuple(found[0])] = presets.kept_sections(found[1], sections)
    size = tuple(presets.load_file(args.layout)[0])
    places = made[size]
    for target in presets.SCREENS:
        laid = made.get(tuple(target))
        how = 'as designed'
        if laid is None:
            laid = presets.fit_layout(places, size, target, sections, text_width, text_ink)
            how = f'fitted from {size[0]}x{size[1]}'
        font = common_font([p.font for p in laid.values() if p.font is not None])  # only where one has none
        write(SHIPPED / presets.file_name(target), presets.preset_data(laid, target, font), how)
    if args.settings is None:
        return 0
    settings = load_settings(Path(args.settings))
    if not settings.presets:
        print(f'no presets in {args.settings}')
        return 1
    for number, kept in settings.presets.items():
        outside = [
            n
            for n, p in kept.items()
            if p.x < 0 or p.y < 0 or p.x + p.width > size[0] or p.y + p.height > size[1]
        ]
        if outside:
            print(f'preset {number}: {", ".join(outside)} not on a {size[0]}x{size[1]} screen at (0, 0)')
            return 1
    starting = presets.starting_data(
        {n: presets.kept_sections(kept, sections) for n, kept in settings.presets.items()},
        size,
        settings.font_size,
        settings.preset_names,
        settings.auto_presets,
    )
    (SHIPPED / presets.STARTING_FOLDER).mkdir(exist_ok=True)
    write(SHIPPED / presets.STARTING_FILE, starting, 'the starting presets')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
