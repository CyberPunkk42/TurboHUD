"""Linux and other systems: what Qt does alone. No system-wide shortcuts yet; the tray
icon's menu switches move mode instead."""


class Native:
    name = 'Linux'

    def prepare_app(self):
        pass

    def raise_window(self, widget):
        return 'always on top through Qt'

    def take_focus(self):
        pass

    def give_focus_back(self):
        pass

    def register_hotkeys(self, on_hotkey):
        return False

    def unregister_hotkeys(self):
        pass
