"""Entry point for ``python -m myai_cli`` and for the bundled ``myai`` binary.

Importing the module and then calling ``entrypoint`` is the same path the installed console
script takes. Running ``main.py`` directly is not: as a script it executes top to bottom, so
its ``if __name__ == "__main__"`` block fires part-way down the file and any command defined
below it never gets registered. That produced a shipped binary whose ``myai projects`` had no
subcommands at all, with nothing failing at build time to say so.
"""

from myai_cli.main import entrypoint

if __name__ == "__main__":
    entrypoint()
