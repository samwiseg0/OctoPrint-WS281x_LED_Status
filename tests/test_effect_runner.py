# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import multiprocessing
import unittest

import mock

from octoprint_ws281x_led_status.runner import EffectRunner

EXAMPLE_SETTINGS = {
    "active_start": "09:00",
    "active_stop": "21:00",
    "strip": {
        "led_invert": True,
        "reverse": False,
        "strip_type": "WS2811_STRIP_GRB",
        "led_brightness": "255",
        "led_count": 255,
        "led_pin": 10,
        "led_freq_hz": 800000,
        "led_dma": 10,
        "led_channel": 0,
    },
    "startup": {"enabled": True, "color": "#ff00ff", "effect": "wipe", "delay": 50},
    "idle": {"enabled": True, "color": "#ff00ff", "effect": "wipe", "delay": 50},
    "disconnected": {
        "enabled": True,
        "color": "#ff00ff",
        "effect": "wipe",
        "delay": 50,
    },
    "progress_print": {"enabled": True, "color": "#ff00ff", "base": "#ff0000"},
    "progress_heatup": {"enabled": True, "color": "#ff00ff", "base": "#ff0000"},
    "progress_cooling": {"enabled": True, "color": "#ff00ff", "base": "#ff0000"},
    "failed": {"enabled": True, "color": "#ff00ff", "effect": "wipe", "delay": 50},
    "success": {"enabled": True, "color": "#ff00ff", "effect": "wipe", "delay": 50},
    "paused": {"enabled": True, "color": "#ff00ff", "effect": "wipe", "delay": 50},
    "printing": {"enabled": True, "color": "#ff00ff", "effect": "wipe", "delay": 50},
    "torch": {"enabled": True, "color": "#ff00ff", "effect": "wipe", "delay": 50},
}


class EffectRunnerTestCase(unittest.TestCase):
    def dont_test_class_instantiate(self):
        self.effect_runner = EffectRunner(
            mock.Mock(), False, multiprocessing.Queue(), EXAMPLE_SETTINGS, "startup"
        )

    @staticmethod
    def setup_mock_ws281x(self):
        mock_ws281x = mock.Mock(PixelStrip)
        return mock_ws281x


def Color(red, green, blue, white=0):
    return (white << 24) | (red << 16) | (green << 8) | blue


class TestFailedException(Exception):
    """Generic TestFailure exception"""


class PixelStrip:
    def __init__(
        self,
        num,
        pin,
        freq_hz=800000,
        dma=10,
        invert=False,
        brightness=255,
        channel=0,
        strip_type=None,
        gamma=None,
    ):
        self.num_pixels = num
        self.pin = pin
        self.freq_hz = freq_hz
        self.dma = dma
        self.invert = invert
        self.brightness = brightness
        self.channel = channel
        self.strip_type = strip_type

    def _cleanup(self):
        pass

    def begin(self):
        pass

    def show(self):
        pass

    def setPixelColor(self, n, color):
        if n > self.num_pixels:
            raise TestFailedException("Tried to set pixel beyond length of strip")

    def setPixelColorRGB(self, n, red, green, blue, white=0):
        if red > 255 or green > 255 or blue > 255 or white > 255:
            raise TestFailedException("Tried to set colour greater than 255")

    def getBrightness(self):
        return self.brightness

    def setBrightness(self, brightness):
        self.brightness = brightness

    def getPixels(self):
        # TODO implement properly? not needed for my plugin
        return

    def numPixels(self):
        return self.num_pixels

    def getPixelColor(self, n):
        return

    def getPixelColorRGB(self, n):
        return

    def getPixelColorRGBW(self, n):
        return
