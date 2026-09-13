"""The certificate the host mints, including on machines whose names break the rules.

These are the cases that only show up on someone else's computer: a hostname longer than
X.509 allows in a common name, a hostname that is not a legal DNS label at all, and an
expired certificate that has to be replaced rather than reused.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from cryptography import x509

from myai_core.security import host_certificate as hc


def test_a_certificate_is_minted_once_and_then_reused(tmp_path: Path) -> None:
    first = hc.load_or_create(tmp_path, addresses=["127.0.0.1"])
    assert first.cert_path.is_file() and first.key_path.is_file()
    assert len(first.fingerprint_sha256) == 64
    assert hc.fingerprint_of_pem(first.cert_path.read_bytes()) == first.fingerprint_sha256

    again = hc.load_or_create(tmp_path, addresses=["127.0.0.1"])
    assert again.fingerprint_sha256 == first.fingerprint_sha256, "a restart must not re-pin"


def test_regenerating_changes_the_fingerprint_so_pinned_devices_must_pair_again(
    tmp_path: Path,
) -> None:
    first = hc.load_or_create(tmp_path, addresses=["127.0.0.1"])
    second = hc.regenerate(tmp_path, addresses=["127.0.0.1"])
    assert second.fingerprint_sha256 != first.fingerprint_sha256


def test_a_hostname_too_long_for_a_common_name_does_not_break_minting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A macOS CI runner's hostname was 67 characters; X.509 allows 64 in a common name.

    The name here is long but legal: every DNS label is within its own 63-character limit,
    so it belongs in the certificate — just not, unabbreviated, in the common name.
    """
    long_name = "runner-" + "x" * 50 + ".ci.internal"
    assert len(long_name) > hc.CN_MAX_CHARS
    assert all(len(label) <= 63 for label in long_name.split("."))
    monkeypatch.setattr(hc.socket, "gethostname", lambda: long_name)

    certificate = hc.regenerate(tmp_path, addresses=["127.0.0.1"])
    parsed = x509.load_pem_x509_certificate(certificate.cert_path.read_bytes())
    common_name = parsed.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
    assert isinstance(common_name, str) and len(common_name) <= hc.CN_MAX_CHARS
    # The full name is still usable as a subject alternative name, which is what matters.
    assert long_name in certificate.subject_names


def test_a_single_label_longer_than_dns_allows_is_left_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 73-character label is not a legal DNS name at all, so it is not put in one."""
    monkeypatch.setattr(hc.socket, "gethostname", lambda: "a" * 73)
    certificate = hc.regenerate(tmp_path, addresses=["127.0.0.1"])
    assert certificate.subject_names == ("localhost", "127.0.0.1")


def test_a_hostname_that_is_not_a_legal_dns_name_is_left_out_rather_than_crashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hc.socket, "gethostname", lambda: "Alex's MacBook Pro")
    certificate = hc.regenerate(tmp_path, addresses=["127.0.0.1"])
    assert "localhost" in certificate.subject_names
    assert "127.0.0.1" in certificate.subject_names
    assert "Alex's MacBook Pro" not in certificate.subject_names


def test_an_expired_certificate_is_replaced_on_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expired = hc.regenerate(tmp_path, addresses=["127.0.0.1"])
    monkeypatch.setattr(
        hc, "_now", lambda: dt.datetime.now(tz=dt.UTC) + dt.timedelta(days=hc.VALIDITY_DAYS + 2)
    )
    replaced = hc.load_or_create(tmp_path, addresses=["127.0.0.1"])
    assert replaced.fingerprint_sha256 != expired.fingerprint_sha256


def test_the_fingerprint_is_shown_in_groups_a_person_can_compare(tmp_path: Path) -> None:
    certificate = hc.load_or_create(tmp_path, addresses=["127.0.0.1"])
    groups = certificate.fingerprint_groups.split(" ")
    assert len(groups) == 16 and all(len(g) == 4 for g in groups)
    assert "".join(groups).lower() == certificate.fingerprint_sha256


def test_the_public_key_pin_is_the_form_pinning_libraries_actually_take(tmp_path: Path) -> None:
    """OkHttp, TrustKit and HPKP all pin the SPKI hash, written 'sha256/<base64>'.

    Computed here the way those libraries compute it — SHA-256 over the DER-encoded
    SubjectPublicKeyInfo — rather than trusting our own helper to agree with itself.
    """
    import base64
    import hashlib

    from cryptography.hazmat.primitives import serialization

    certificate = hc.load_or_create(tmp_path, addresses=["127.0.0.1"])
    parsed = x509.load_pem_x509_certificate(certificate.cert_path.read_bytes())
    spki = parsed.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    expected = base64.b64encode(hashlib.sha256(spki).digest()).decode()

    assert certificate.public_key_sha256 == expected
    assert certificate.public_key_pin == f"sha256/{expected}"
    assert hc.public_key_sha256_of_pem(certificate.cert_path.read_bytes()) == expected


def test_the_key_pin_and_the_certificate_fingerprint_are_different_things(tmp_path: Path) -> None:
    """Two pins with two readers: one for a person's eyes, one for a pinning library.

    A new certificate over a new key changes both, which is what 'reset it' has to mean.
    """
    first = hc.load_or_create(tmp_path, addresses=["127.0.0.1"])
    assert first.public_key_sha256 != first.fingerprint_sha256

    second = hc.regenerate(tmp_path, addresses=["127.0.0.1"])
    assert second.fingerprint_sha256 != first.fingerprint_sha256
    assert second.public_key_sha256 != first.public_key_sha256


def test_local_addresses_always_include_loopback() -> None:
    addresses = hc.local_addresses()
    assert addresses and addresses[0] == "127.0.0.1"
    assert len(addresses) == len(set(addresses))
