"""Versioned device-key backends — software fallback vs hardware-backed adapters.

Honest security model
---------------------
Current production-path identity material is **software-backed**: private keys are
exportable if an attacker can read the OS keychain / local secret store. That
establishes cryptographic device identity for X25519 sealed DEKs and challenge
signing, but does **not** establish hardware binding.

Hardware backends (Secure Enclave on macOS, TPM on Windows) are stubbed as
adapters. They must wrap or derive keys via platform APIs — never invent custom
crypto. Where the platform cannot provide X25519 in hardware, use a versioned
key-agreement adapter (e.g. ECDH P-256 via SE/TPM) and seal a software X25519
keypair under that hardware secret.

Guarantees by binding mode
--------------------------
| Mode      | Private key exportable? | Survives directory copy? | Survives VM clone? |
|-----------|-------------------------|--------------------------|--------------------|
| software  | Yes (file/keychain)     | Usually yes              | Usually yes        |
| keyring   | OS-dependent            | Often no                 | Often yes          |
| hardware  | No (when available)     | No                       | Platform-dependent |

Do not advertise hardware binding until a backend returns ``binding='hardware'``
and the stress-suite items for that platform are verified.
"""

from __future__ import annotations

import json
import os
import platform
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class BindingMode(str, Enum):
    SOFTWARE = "software"
    KEYRING = "keyring"
    HARDWARE = "hardware"


@dataclass(frozen=True)
class BackendCapabilities:
    backend_id: str
    binding: BindingMode
    exportable_private_keys: bool
    hardware_available: bool
    guarantees: str
    limitations: str
    platform: str


class DeviceKeyBackend(ABC):
    backend_id: str

    @abstractmethod
    def capabilities(self) -> BackendCapabilities: ...

    @abstractmethod
    def store_blob(self, name: str, value: str) -> None: ...

    @abstractmethod
    def load_blob(self, name: str) -> str | None: ...


class SoftwareFileBackend(DeviceKeyBackend):
    """Local encrypted-at-rest JSON via secrets_store fallback path.

    Used when STUDIO_FORCE_LOCAL_SECRETS=1 or keyring is unavailable.
    Reduced security: copying the studio data dir copies the private keys.
    """

    backend_id = "software-file-v1"

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            backend_id=self.backend_id,
            binding=BindingMode.SOFTWARE,
            exportable_private_keys=True,
            hardware_available=False,
            guarantees=(
                "Cryptographic challenge/response and X25519 sealed DEKs bind licences "
                "to this keypair. File permissions restrict casual access."
            ),
            limitations=(
                "Private keys are exportable. Copying the application data directory "
                "or secret store clones the device identity. Not hardware-backed."
            ),
            platform=sys.platform,
        )

    def store_blob(self, name: str, value: str) -> None:
        from studio.secrets_store import set_secret

        # Force local file path semantics for this backend
        os.environ.setdefault("STUDIO_FORCE_LOCAL_SECRETS", "1")
        set_secret(name, value)

    def load_blob(self, name: str) -> str | None:
        from studio.secrets_store import get_secret

        return get_secret(name)


class OsKeyringBackend(DeviceKeyBackend):
    """OS credential store via keyring (still typically software-exportable)."""

    backend_id = "os-keyring-v1"

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            backend_id=self.backend_id,
            binding=BindingMode.KEYRING,
            exportable_private_keys=True,  # most desktop keyrings allow export by owner
            hardware_available=False,
            guarantees=(
                "Keys live in the OS credential store rather than a plain workspace file "
                "when keyring is available and STUDIO_FORCE_LOCAL_SECRETS is unset."
            ),
            limitations=(
                "Not Secure Enclave / TPM. An attacker with the user's unlocked session "
                "can often export credentials. VM clones may retain keyring contents."
            ),
            platform=sys.platform,
        )

    def store_blob(self, name: str, value: str) -> None:
        from studio.secrets_store import set_secret

        set_secret(name, value)

    def load_blob(self, name: str) -> str | None:
        from studio.secrets_store import get_secret

        return get_secret(name)


class HardwareBackendStub(DeviceKeyBackend):
    """Placeholder for Secure Enclave / TPM adapters — not yet production-ready.

    Detection only. Raising on store/load prevents accidental claims of HW binding.
    """

    backend_id = "hardware-stub-v1"

    def capabilities(self) -> BackendCapabilities:
        plat = sys.platform
        hw = False
        note = "No hardware adapter implemented for this host."
        if plat == "darwin":
            note = (
                "macOS Secure Enclave adapter planned (CryptoKit / Secure Enclave "
                "P-256 key agreement wrapping software X25519). Not implemented."
            )
        elif plat.startswith("win"):
            note = (
                "Windows TPM / CNG adapter planned (NCrypt ECDH wrapping software "
                "X25519). Not implemented."
            )
        elif plat.startswith("linux"):
            note = (
                "Linux TPM2 adapter optional via tpm2-pytss; not implemented. "
                "Default remains software/keyring."
            )
        return BackendCapabilities(
            backend_id=self.backend_id,
            binding=BindingMode.HARDWARE,
            exportable_private_keys=False,
            hardware_available=hw,
            guarantees="None until a real hardware adapter is shipped and stress-tested.",
            limitations=note,
            platform=plat,
        )

    def store_blob(self, name: str, value: str) -> None:
        raise NotImplementedError(
            "Hardware-backed device identity is not available on this build. "
            "Use software or keyring backends. See PROTECTION_ROADMAP.md."
        )

    def load_blob(self, name: str) -> str | None:
        raise NotImplementedError(
            "Hardware-backed device identity is not available on this build."
        )


def select_device_backend() -> DeviceKeyBackend:
    """Choose the strongest *implemented* backend for this process.

    Prefer keyring when available; otherwise software file. Never silently select
    the hardware stub for live key storage.
    """
    prefer = os.environ.get("STUDIO_DEVICE_BACKEND", "").strip().lower()
    if prefer in {"software", "file"}:
        return SoftwareFileBackend()
    if prefer in {"hardware", "se", "tpm"}:
        # Explicit request — still stub; callers must handle NotImplementedError
        return HardwareBackendStub()
    if prefer in {"keyring", "os"}:
        return OsKeyringBackend()

    if os.environ.get("STUDIO_FORCE_LOCAL_SECRETS") == "1":
        return SoftwareFileBackend()

    try:
        import keyring  # type: ignore

        if keyring is not None:
            return OsKeyringBackend()
    except Exception:
        pass
    return SoftwareFileBackend()


def describe_device_security() -> dict[str, Any]:
    backend = select_device_backend()
    caps = backend.capabilities()
    hw_stub = HardwareBackendStub().capabilities()
    return {
        "active_backend": caps.backend_id,
        "binding": caps.binding.value,
        "exportable_private_keys": caps.exportable_private_keys,
        "guarantees": caps.guarantees,
        "limitations": caps.limitations,
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "hardware_adapter": {
            "status": "not_implemented",
            "backend_id": hw_stub.backend_id,
            "notes": hw_stub.limitations,
        },
        "honest_claim": (
            "Device identity today is cryptographic software identity, not "
            "hardware-backed non-exportable identity."
        ),
    }


def identity_envelope(identity_json: str, *, binding: BindingMode, backend_id: str) -> str:
    """Wrap legacy identity JSON with versioned binding metadata."""
    data = json.loads(identity_json)
    if "v" not in data:
        data = {
            "v": 1,
            "binding": binding.value,
            "backend_id": backend_id,
            "identity": data,
        }
    return json.dumps(data, separators=(",", ":"))


def unwrap_identity_envelope(raw: str) -> tuple[str, BindingMode, str]:
    data = json.loads(raw)
    if "identity" in data and "v" in data:
        return (
            json.dumps(data["identity"], separators=(",", ":")),
            BindingMode(data.get("binding", BindingMode.SOFTWARE.value)),
            str(data.get("backend_id", "legacy")),
        )
    # Legacy flat storage
    return raw, BindingMode.SOFTWARE, "legacy-flat-v0"
