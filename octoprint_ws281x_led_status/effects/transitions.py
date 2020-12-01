# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from octoprint_ws281x_led_status.util import q_poll_milli_sleep


def fade_in(strip, fade_q, start_brightness, target_brightness, delay):
    # sanity check:
    if start_brightness > target_brightness:
        print("idiot")
        return

    current_brightness = 0
    while current_brightness < target_brightness:
        print(current_brightness)
        strip.setBrightness(current_brightness)
        current_brightness += 1
        # interrupted by a new transition
        if not q_poll_milli_sleep(delay, fade_q):
            return


def fade_out(strip, fade_q, start_brightness, target_brightness, delay):
    # sanity check:
    if start_brightness < target_brightness:
        print("idiot")
        return

    current_brightness = target_brightness
    while current_brightness > 0:
        print(current_brightness)
        strip.setBrightness(current_brightness)
        current_brightness -= 1
        # interrupted by a new transition
        if not q_poll_milli_sleep(delay, fade_q):
            return
