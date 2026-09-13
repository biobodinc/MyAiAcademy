"""The certificate the host presents when you let a phone reach it (spec §52, §55).

Why a self-signed certificate, and why that is not a compromise
--------------------------------------------------------------

A phone talking to a computer on the same home network cannot use the ordinary web trust
model. There is no public hostname to get a certificate for, no certificate authority will
issue one for ``192.168.1.24``, and the address changes with the network. The usual
response — plain HTTP on the LAN, "it's your own network" — would put the credential and
every message of the conversation in the clear for anyone else on that Wi-Fi, which is not
something this program is willing to do.

So the host mints its own certificate and the phone pins it: the pairing code and the
certificate's SHA-256 fingerprint travel together in the QR code, over the air gap of the
user looking at their own screen. From then on the phone accepts exactly one certificate —
this host's — and rejects everything else, including a genuine certificate from a real
authority. That is stronger than the web's model here, not weaker: there is no authority
that could be persuaded to issue a certificate for this host to somebody else.

The private key never leaves the machine, is written owner-only, and is regenerated (with a
new fingerprint, invalidating pinned copies) whenever the user asks.

Two pins, for two different readers
-----------------------------------

The certificate's SHA-256 fingerprint is what a *person* compares: it is shown in groups of
four on both screens, and it identifies this exact certificate.

Every pinning implementation a phone can actually use — OkHttp's ``CertificatePinner`` on
Android, TrustKit on iOS, and the HPKP-style syntax both inherit — pins something else: the
SHA-256 of the DER-encoded *Subject Public Key Info*, base64-encoded, written
``sha256/AAAA...``. So the host publishes that too. Pinning the key rather than the
certificate also means a renewal that keeps the same key does not force every device to
pair again, which is the behaviour those libraries were designed around.
"""

from __future__ import annotations

import base64
import datetime as dt
import ipaddress
import re
import socket
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from myai_core.security.storage_checks import restrict_new_file

CN_MAX_CHARS = 64
"""X.509 caps a CommonName at 64 characters; some machines have longer hostnames."""
_DNS_NAME = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9-]{1,63})*$")

CERT_FILE = "host-cert.pem"
KEY_FILE = "host-key.pem"
VALIDITY_DAYS = 825
"""The longest a self-signed leaf is customarily accepted. Renewal re-pins, deliberately."""


@dataclass(frozen=True, slots=True)
class HostCertificate:
    cert_path: Path
    key_path: Path
    fingerprint_sha256: str
    """Lower-case hex, no separators. This is the certificate, and what a person compares."""
    public_key_sha256: str
    """Base64 SHA-256 of the DER SubjectPublicKeyInfo: what a pinning library consumes."""
    not_after: dt.datetime
    subject_names: tuple[str, ...]

    @property
    def fingerprint_groups(self) -> str:
        """The fingerprint in readable pairs, for someone comparing it by eye."""
        return " ".join(
            self.fingerprint_sha256[i : i + 4].upper()
            for i in range(0, len(self.fingerprint_sha256), 4)
        )

    @property
    def public_key_pin(self) -> str:
        """The public key pin as OkHttp, TrustKit and HPKP all spell it."""
        return f"sha256/{self.public_key_sha256}"


def local_addresses() -> list[str]:
    """Addresses this machine might be reachable on, best effort and never guessed.

    Uses a UDP socket that is never sent on: connecting a datagram socket only asks the
    routing table which local address would be used to reach that destination.
    """
    found: list[str] = ["127.0.0.1"]
    for probe in ("8.8.8.8", "1.1.1.1"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(0.2)
                sock.connect((probe, 53))
                address = sock.getsockname()[0]
        except OSError:
            continue
        if address and address not in found:
            found.append(address)
            break
    return found


def load_or_create(data_dir: Path, *, addresses: list[str] | None = None) -> HostCertificate:
    """Return the host certificate, minting one on first use or when it has expired."""
    cert_path = data_dir / CERT_FILE
    key_path = data_dir / KEY_FILE
    existing = _read(cert_path, key_path)
    if existing is not None and existing.not_after > _now() + dt.timedelta(days=1):
        return existing
    return regenerate(data_dir, addresses=addresses)


def regenerate(data_dir: Path, *, addresses: list[str] | None = None) -> HostCertificate:
    """Mint a new certificate and key. Any phone pinned to the old one must pair again."""
    data_dir.mkdir(parents=True, exist_ok=True)
    cert_path = data_dir / CERT_FILE
    key_path = data_dir / KEY_FILE
    names = addresses if addresses is not None else local_addresses()
    hostname = socket.gethostname() or "myai-host"

    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name(
        [
            # The common name is cosmetic here — a device pins the fingerprint, not a name —
            # but it still has to be a legal one, and a machine's hostname can exceed the
            # 64-character limit. A CI runner's did, which is how this was found.
            x509.NameAttribute(NameOID.COMMON_NAME, hostname[:CN_MAX_CHARS]),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MyAI Academy"),
        ]
    )
    alt_names: list[x509.GeneralName] = [x509.DNSName("localhost")]
    if _DNS_NAME.match(hostname) and len(hostname) <= 253:
        alt_names.append(x509.DNSName(hostname))
    for address in names:
        try:
            alt_names.append(x509.IPAddress(ipaddress.ip_address(address)))
        except ValueError:
            if _DNS_NAME.match(address):
                alt_names.append(x509.DNSName(address))

    now = _now()
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))  # tolerate a little clock skew
        .not_valid_after(now + dt.timedelta(days=VALIDITY_DAYS))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    restrict_new_file(key_path)
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return _describe(certificate, cert_path, key_path)


def fingerprint_of_pem(pem: bytes) -> str:
    return x509.load_pem_x509_certificate(pem).fingerprint(hashes.SHA256()).hex()


def public_key_sha256_of_pem(pem: bytes) -> str:
    """The base64 SPKI pin for a PEM certificate, as a pinning library would compute it."""
    return _public_key_sha256(x509.load_pem_x509_certificate(pem))


def _public_key_sha256(certificate: x509.Certificate) -> str:
    spki = certificate.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    digest = hashes.Hash(hashes.SHA256())
    digest.update(spki)
    return base64.b64encode(digest.finalize()).decode("ascii")


def _read(cert_path: Path, key_path: Path) -> HostCertificate | None:
    if not (cert_path.is_file() and key_path.is_file()):
        return None
    try:
        certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
    except (OSError, ValueError):
        return None
    return _describe(certificate, cert_path, key_path)


def _describe(certificate: x509.Certificate, cert_path: Path, key_path: Path) -> HostCertificate:
    try:
        san = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        names = tuple(str(name.value) for name in san.value)
    except x509.ExtensionNotFound:  # pragma: no cover - our own certificates always have one
        names = ()
    return HostCertificate(
        cert_path=cert_path,
        key_path=key_path,
        fingerprint_sha256=certificate.fingerprint(hashes.SHA256()).hex(),
        public_key_sha256=_public_key_sha256(certificate),
        not_after=certificate.not_valid_after_utc,
        subject_names=names,
    )


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)
