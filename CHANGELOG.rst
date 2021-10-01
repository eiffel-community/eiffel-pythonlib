=========
Changelog
=========

Version 2.2.0
-------------

- Add sepia routing keys to eiffellib

Version 2.1.0
-------------

- Specify open dependencies

Version 2.0.1
-------------

- Version 2.0.0 did not work as expected. This fixes the problem with 2.0.0

Version 2.0.0
-------------

- Make the pika dependency optional

Version 1.2.0
-------------

- Update event schemas
- Add badge to eiffel-pythonlib

Version 1.1.1
-------------

- Add wildcard support to nackable subscriptions

Version 1.1.0
-------------

- If Context is None, call a subscriber with None on Context.
- We should use the python standard library's logging module to log messages, not print or traceback.print_exc()
- Reconnect the connection thread if broker shuts down

Version 1.0.2
-------------

- Fix examples
- Add Fredrik as contributor
- Correct library name for the package when building wheel
- Re-added examples without unsupported rst options

Version 1.0.1
-------------

- 1.0.0 did not upload correctly to pypi.

Version 1.0.0
-------------

- Eiffel library for sending and retrieving events.
