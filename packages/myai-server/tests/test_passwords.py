"""The password hashing, checked for the properties that matter rather than its output."""

from __future__ import annotations

import pytest

from myai_server import passwords

PASSWORD = "correct horse battery staple"
# Deliberately feeble parameters. These tests care about the shape of the scheme, and paying
# 64 MiB of real Argon2 work per assertion would make the suite unpleasant to run.
FAST = passwords.HashParams(memory_kib=8, iterations=1, lanes=1)


def test_a_hash_verifies():
    encoded = passwords.hash_password(PASSWORD, FAST)
    assert passwords.verify_password(PASSWORD, encoded)


def test_a_wrong_password_does_not_verify():
    encoded = passwords.hash_password(PASSWORD, FAST)
    assert not passwords.verify_password("something else entirely", encoded)


def test_the_password_is_not_recoverable_from_the_hash():
    encoded = passwords.hash_password(PASSWORD, FAST)
    assert PASSWORD not in encoded
    assert "horse" not in encoded


def test_the_same_password_hashes_differently_every_time():
    """Salted, so identical passwords do not produce identical rows."""
    first = passwords.hash_password(PASSWORD, FAST)
    second = passwords.hash_password(PASSWORD, FAST)
    assert first != second
    assert passwords.verify_password(PASSWORD, first)
    assert passwords.verify_password(PASSWORD, second)


def test_the_cost_is_recorded_in_the_hash():
    encoded = passwords.hash_password(PASSWORD, passwords.HashParams(8, 1, 1))
    assert "$argon2id$" in encoded
    assert "m=8,t=1,p=1" in encoded


def test_a_hash_made_with_weaker_parameters_still_verifies():
    """Raising the defaults must not lock out everyone who signed up before."""
    old = passwords.hash_password(PASSWORD, passwords.HashParams(8, 1, 1))
    assert passwords.verify_password(PASSWORD, old)
    assert passwords.needs_rehash(old)


def test_a_hash_at_the_current_cost_does_not_need_rehashing():
    encoded = passwords.hash_password(PASSWORD)
    assert not passwords.needs_rehash(encoded)


@pytest.mark.parametrize("stored", [None, "", "not a hash", "$argon2id$broken"])
def test_a_missing_or_unreadable_hash_refuses_rather_than_raising(stored):
    """An OAuth account has no password. Asking about one must not blow up the request."""
    assert not passwords.verify_password(PASSWORD, stored)
    assert passwords.needs_rehash(stored)


def test_an_empty_password_never_verifies():
    encoded = passwords.hash_password(PASSWORD, FAST)
    assert not passwords.verify_password("", encoded)


def test_an_empty_password_cannot_be_set():
    with pytest.raises(ValueError):
        passwords.hash_password("")
