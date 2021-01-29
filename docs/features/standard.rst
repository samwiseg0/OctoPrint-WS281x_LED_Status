.. _sec-features-standard:

Standard effect options
=======================

The plugin allows you to configure effects that will be shown on specific OctoPrint or printer states. For each effect,
there is configuration for:

* Effect

  Can be one of the :ref:`standard effects <sec-effects-standard>` available in the plugin

* Color

  The base color to use for effects run from the plugin
  .. note::
     For some effects, such as rainbow, the colour is ignored.

* Delay

  The length of time, in milliseconds to wait between effect frames. For some effects this may be
  higher, others quite low.


.. _sec-features-standard-events:

Tracked events
--------------

The plugin will react to events on each of the following events. Some have more configuration
available, noted per-effect.

* Connected
*
