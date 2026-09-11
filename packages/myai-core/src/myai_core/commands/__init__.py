"""Slash-command interpreter (spec §36–§39, §81).

The parser is pure and fully unit-tested. Execution is delegated to
:mod:`myai_core.commands.dispatcher`, which in Phase 1 can answer status/hardware/help
style commands and *honestly* reports that learning/training are not available yet.
"""
