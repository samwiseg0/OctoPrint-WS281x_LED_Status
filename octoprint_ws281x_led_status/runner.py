# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
import re
import threading
import time

try:
    from queue import Queue
except ImportError:
    from Queue import Queue  # Python 2 uses Queue, not queue...

import rpi_ws281x
from rpi_ws281x import PixelStrip

from octoprint_ws281x_led_status.effects import progress, standard, transitions
from octoprint_ws281x_led_status.util import hex_to_rgb

KILL_MSG = "KILL"
STRIP_SETTINGS = [  # ALL LED SETTINGS, for rpi_ws281x.PixelStrip
    "led_count",
    "led_pin",
    "led_freq_hz",
    "led_dma",
    "led_invert",
    "led_brightness",
    "led_channel",
    "strip_type",
    "reverse",
]
STRIP_TYPES = {  # Adding any more strips requires a request, then testing
    "WS2811_STRIP_GRB": rpi_ws281x.WS2811_STRIP_GRB,
    "WS2812_STRIP": rpi_ws281x.WS2812_STRIP,
    "WS2811_STRIP_RGB": rpi_ws281x.WS2811_STRIP_RGB,
    "WS2811_STRIP_RBG": rpi_ws281x.WS2811_STRIP_RBG,
    "WS2811_STRIP_GBR": rpi_ws281x.WS2811_STRIP_GBR,
    "WS2811_STRIP_BGR": rpi_ws281x.WS2811_STRIP_BGR,
    "WS2811_STRIP_BRG": rpi_ws281x.WS2811_STRIP_BRG,
    "SK6812_STRIP": rpi_ws281x.SK6812_STRIP,
    "SK6812W_STRIP": rpi_ws281x.SK6812W_STRIP,
    "SK6812_STRIP_RGBW": rpi_ws281x.SK6812_STRIP_RGBW,
    "SK6812_STRIP_RBGW": rpi_ws281x.SK6812_STRIP_RBGW,
    "SK6812_STRIP_GRBW": rpi_ws281x.SK6812_STRIP_GRBW,
    "SK6812_STRIP_GBRW": rpi_ws281x.SK6812_STRIP_GBRW,
    "SK6812_STRIP_BRGW": rpi_ws281x.SK6812_STRIP_BRGW,
    "SK6812_STRIP_BGRW": rpi_ws281x.SK6812_STRIP_BGRW,
}
EFFECTS = {
    "solid": standard.solid_color,
    "wipe": standard.color_wipe,
    "wipe2": standard.color_wipe_2,
    "pulse": standard.simple_pulse,
    "rainbow": standard.rainbow,
    "cycle": standard.rainbow_cycle,
    "bounce": standard.bounce,
    "bounce_solo": standard.solo_bounce,
    "random": standard.random_single,
    "blink": standard.blink,
    "cross": standard.crossover,
    "balls": standard.bouncy_balls,
    "progress_print": progress.progress,
    "progress_heatup": progress.progress,
    "progress_cooling": progress.progress,
}
MODES = [
    "startup",
    "idle",
    "disconnected",
    "progress_print",
    "progress_heatup",
    "progress_cooling",
    "failed",
    "success",
    "paused",
    "printing",
    "torch",
]

# Example command: M150 R10 G200 B300
# more -> https://github.com/cp2004/OctoPrint-WS281x_LED_Status/wiki/Features#m150-intercept
M150_REGEX = (
    r"(^|[^A-Za-z])[Rr](?P<red>\d{1,3})|(^|[^A-Za-z])[GgUu](?P<green>\d{1,3})|(^|[^A-Za-z])"
    r"[Bb](?P<blue>\d{1,3})|(^|[^A-Za-z])[Pp](?P<brightness>\d{1,3})|(^|[^A-Za-z])[Ww](?P<white>\d{1,3})"
)


class EffectRunner:
    def __init__(self, log_path, debug, queue, all_settings, previous_state):
        self._logger = logging.getLogger("octoprint.plugins.ws281x_led_status.debug")
        self.setup_custom_logger(log_path, debug)
        self.settings = all_settings
        self.reverse = all_settings["strip"]["reverse"]
        self.max_brightness = all_settings["strip"]["led_brightness"]
        self.fade_in_enabled = all_settings["fade"]["in"]
        self.fade_out_enabled = all_settings["fade"]["out"]
        self.fade_time = int(all_settings["fade"]["time"])

        self.fade_thread = None
        self.fade_queue = Queue()
        self.lights_on = True

        self.previous_state = (
            previous_state if previous_state is not None else "startup"
        )

        if not self.settings["active_start"] or not self.settings["active_stop"]:
            self.start_time = None
            self.end_time = None
        else:
            start = (
                self.settings["active_start"].split(":")
                if self.settings["active_start"]
                else None
            )
            end = (
                self.settings["active_stop"].split(":")
                if self.settings["active_stop"]
                else None
            )
            self.start_time = (int(start[0]) * 60) + int(start[1])
            self.end_time = (int(end[0]) * 60) + int(end[1])
        self.active_times_state = True

        self.queue = queue
        self.strip = self.start_strip()
        if not self.strip:
            self._logger.info("No strip initialised, exiting the effect process.")
            return

        if debug:
            self.log_settings()
        else:
            self._logger.info(
                "Debug logging not enabled, if you are reporting issues please enable it under 'Features' in the settings page."
            )
        self.main_loop()

    def setup_custom_logger(self, path, debug):
        from octoprint.logging.handlers import CleaningTimedRotatingFileHandler

        # Cleaning handler will remove old logs, defined by 'backupCount'
        # 'D' specifies to roll over each day
        effect_runner_handler = CleaningTimedRotatingFileHandler(
            path, when="D", backupCount=2
        )
        effect_runner_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
        )
        effect_runner_handler.setLevel(logging.DEBUG)

        self._logger.addHandler(effect_runner_handler)
        self._logger.setLevel(logging.DEBUG if debug else logging.INFO)
        self._logger.propagate = False

    def log_settings(self):
        """
        This has to be here so I can find out what kind of settings people
        are running when they report issues. Only logged in debug mode.
        :return: None
        """
        line = "Current settings:"

        # Start with strip settings
        line = line + "\n | * STRIP SETTINGS *"
        for key, value in self.settings["strip"].items():
            line = line + "\n | - " + str(key) + ": " + str(value)

        # effect settings
        line = line + "\n | * EFFECT SETTINGS *"
        for key, value in self.settings.items():
            if key in MODES:
                line = line + "\n | " + str(key)
                for setting_key, setting_value in self.settings[key].items():
                    line = (
                        line + "\n | - " + str(setting_key) + ": " + str(setting_value)
                    )

        # extras
        line = line + "\n | * ACTIVE TIMES *"
        line = line + "\n | - start: " + str(self.settings["active_start"])
        line = line + "\n | - end: " + str(self.settings["active_stop"])
        self._logger.debug(line)

    def main_loop(self):
        try:
            msg = self.previous_state
            while True:
                if not self.queue.empty():
                    msg = self.queue.get()  # The ONLY place the queue should be 'got'
                if msg:
                    parsed = self.parse_q_msg(msg)  # Effects are run from parse_q_msg
                    if parsed == KILL_MSG:
                        return
                    elif parsed:
                        msg = parsed  # So that previous state can return after 'lights on'
                else:
                    self.startup_effect()
        except KeyboardInterrupt:
            self.blank_leds()
            return

    def parse_q_msg(self, msg):
        if not msg:
            self.startup_effect()  # Will probably never happen, but just in case
        if msg == KILL_MSG:
            self.blank_leds()
            self._logger.info("Kill message recieved, Bye!")
            return msg
        elif msg == "on":
            self.lights_on = True
            self._logger.info("On message recieved, turning on LEDs")
            if self.fade_in_enabled:
                self._logger.debug("Starting fade in for {}ms".format(self.fade_time))
                self.start_fade("in")
            return self.previous_state
        elif msg == "off":
            self.lights_on = False
            self._logger.info("Off message recieved, turning off LEDs")
            if self.fade_out_enabled:
                self._logger.debug("Starting fade out for {}ms".format(self.fade_time))
                self.start_fade("out")
            return self.previous_state
        elif "progress" in msg:
            msg_split = msg.split()
            self.progress_effect(msg_split[0], float(msg_split[1]))
            if msg != self.previous_state:
                self._logger.debug(
                    "Recieved message to update progress: {}".format(msg)
                )
            self.previous_state = msg
        elif "M150" in msg:
            self.parse_m150(msg)
            self.previous_state = msg
        else:
            self.standard_effect(msg)
            if msg != self.previous_state:
                self._logger.debug("Recieved message to change effect: {}".format(msg))
            self.previous_state = msg

    def parse_m150(self, msg):
        # Start at 0, means sending 'M150' with no params turns LEDs off
        red = green = blue = 0
        red_included = green_included = blue_included = False
        brightness = self.max_brightness  # No 'P' param? Use set brightness
        matches = re.finditer(M150_REGEX, msg)
        for match in matches:
            if match.group("red"):
                red = min(int(match.group("red")), 255)
                red_included = True
            elif match.group("green"):
                green = min(int(match.group("green")), 255)
                green_included = True
            elif match.group("blue"):
                blue = min(int(match.group("blue")), 255)
                blue_included = True
            elif match.group("white"):
                # See issue #33 for details of why this was changed. R/G/B params take priority over white, rather than
                # the other way (w max priority). For compatibility with https://github.com/horfee/OctoPrint-M150control
                if not red_included and not blue_included and not green_included:
                    red = green = blue = min(int(match.group("white")), 255)
            elif match.group("brightness"):
                brightness = min(int(match.group("brightness")), 255)

        if self.check_times() and self.lights_on:  # Respect lights on/off
            EFFECTS["solid"](
                self.strip, self.queue, (red, green, blue), max_brightness=brightness
            )
        else:
            self.blank_leds()

    def startup_effect(self):
        if self.previous_state != "startup":
            self._logger.debug("Hello! Running startup effect")
        self.standard_effect("startup")
        self.previous_state = "startup"

    def progress_effect(self, mode, value):
        if self.fade_thread and self.fade_thread.is_alive():
            fade = True
        else:
            fade = False
        if self.check_times() and self.lights_on:
            effect_settings = self.settings[mode]
            EFFECTS[mode](
                self.strip,
                self.queue,
                int(value),
                hex_to_rgb(effect_settings["color"]),
                hex_to_rgb(effect_settings["base"]),
                self.max_brightness,
                self.reverse,
                fade=fade,
            )
        else:
            self.blank_leds()

    def standard_effect(self, mode):
        if self.fade_thread and self.fade_thread.is_alive():
            fade = True
        else:
            fade = False
        if self.check_times() and self.lights_on:
            effect_settings = self.settings[mode]
            EFFECTS[effect_settings["effect"]](
                self.strip,
                self.queue,
                hex_to_rgb(effect_settings["color"]),
                effect_settings["delay"],
                self.max_brightness,
                fade=fade,
            )
        else:
            self.blank_leds()

    def blank_leds(self):
        """Set LEDs to off, wait 0.1secs to prevent CPU burn"""
        EFFECTS["solid"](
            self.strip,
            self.queue,
            [0, 0, 0],
            max_brightness=self.max_brightness,
            wait=False,
        )
        if self.queue.empty():
            time.sleep(0.1)

    def start_fade(self, style):
        if style == "in":
            enabled = self.fade_in_enabled
            target_transition = transitions.fade_in
            start_brightness = 0
            target_brightness = self.max_brightness

        else:
            enabled = self.fade_out_enabled
            target_transition = transitions.fade_out
            start_brightness = self.max_brightness
            target_brightness = 0

        if not enabled:  # sanity check - should have been dealt with already
            return

        # Scale brightness steps across time - calculates time for each step
        delay = int(self.fade_time / self.max_brightness)
        # Stop any current fades, but record what brightness the strip is at
        if self.fade_thread and self.fade_thread.is_alive():
            self.fade_queue.put(KILL_MSG)
            self.fade_thread.join()
            # We were likely fading already - so start from there.
            start_brightness = self.strip.getBrightness()

        self.fade_thread = threading.Thread(
            target=target_transition,
            name="WS281x Fade transition",
            args=(
                self.strip,
                self.fade_queue,
                start_brightness,
                target_brightness,
                delay,
            ),
        )
        self.fade_thread.daemon = True
        self.fade_thread.start()

    def check_times(self):
        """Check if current time is within 'active times' configuration, log if change detected"""
        if (
            not self.start_time or not self.end_time
        ):  # Active times are disabled, LEDs always on
            return True
        current_time = time.ctime(time.time()).split()[3].split(":")
        ct_mins = (int(current_time[0]) * 60) + int(current_time[1])

        if self.start_time <= ct_mins < self.end_time:
            if not self.lights_on:
                self._logger.debug(
                    "Active time start reached, but toggle switch is off"
                )
            if not self.active_times_state:
                self._logger.debug("Active time start reached")
                self.active_times_state = True
            return True
        else:
            if self.active_times_state:
                self._logger.debug("Active times end reached")
                self.active_times_state = False
            return False

    def start_strip(self):
        """
        Start PixelStrip object
        :returns rpi_ws281x.PixelStrip
        """
        self._logger.info("Initialising LED strip")
        strip_settings = self.settings["strip"]
        try:
            strip = PixelStrip(
                num=strip_settings["led_count"],
                pin=strip_settings["led_pin"],
                freq_hz=strip_settings["led_freq_hz"],
                dma=strip_settings["led_dma"],
                invert=strip_settings["led_invert"],
                brightness=strip_settings["led_brightness"],
                channel=strip_settings["led_channel"],
                strip_type=STRIP_TYPES[strip_settings["strip_type"]],
            )
            strip.begin()
            self._logger.info("Strip successfully initialised")
            return strip
        except Exception as e:  # Probably wrong settings...
            self._logger.error("Strip failed to initialize, no effects will be run.")
            self._logger.error("Please check your settings.")
            self._logger.error("Here's the exception: {}".format(e))
            return None
