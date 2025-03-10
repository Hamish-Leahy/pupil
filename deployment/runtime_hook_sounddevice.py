"""Workaround to find sounddevice on Linux during runtime

See this issue for details:
https://github.com/spatialaudio/python-sounddevice/issues/130#issuecomment-1367883016
"""

import ctypes.util
import functools
import logging

class SoundDevicePatcher:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.original_find_library = ctypes.util.find_library
        self.patch_library()

    def patch_library(self):
        @functools.wraps(self.original_find_library)
        def _find_library_patched(name):
            if name == "portaudio":
                return "libportaudio.so.2"
            return self.original_find_library(name)

        ctypes.util.find_library = _find_library_patched
        self.logger.debug("Patched `ctypes.util.find_library` to find sounddevice.")

    def restore_library(self):
        ctypes.util.find_library = self.original_find_library
        self.logger.debug("Restored original `ctypes.util.find_library`.")

def main():
    patcher = SoundDevicePatcher()
    import sounddevice  # Attempt to import sounddevice after patching
    patcher.restore_library()
    patcher.logger.info("sounddevice import successful!")

if __name__ == "__main__":
    main()
