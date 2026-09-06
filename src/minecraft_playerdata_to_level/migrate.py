"""Core NBT migration and safe output handling."""

from __future__ import annotations

import os
import tempfile
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import gzip

import nbtlib
from nbtlib.tag import Compound


class MigrationError(Exception):
    """Raised when an input file does not have the expected Minecraft structure."""


_NEOFORGE_WITH_MARKER = bytes.fromhex("09 00 04 77 69 74 68 0a 00 00 00 03")
_NEOFORGE_BAD_SEQUENCE = bytes.fromhex("00 08 00 00 00 08 00 05 63 6f 6c 6f 72")
_NEOFORGE_FIXED_SEQUENCE = bytes.fromhex("00 08 00 05 63 6f 6c 6f 72")


def _parse_nbt(raw: bytes) -> nbtlib.File:
    return nbtlib.File.parse(BytesIO(raw))


def _repair_known_modded_nbt(raw: bytes) -> bytes:
    matches = [
        index
        for index in range(len(raw))
        if raw.startswith(_NEOFORGE_BAD_SEQUENCE, index)
    ]
    if len(matches) != 1:
        raise MigrationError(
            "playerdata contains unsupported malformed NBT; expected one known "
            "NeoForge Apotheosis component encoding"
        )

    index = matches[0]
    marker_index = raw.rfind(_NEOFORGE_WITH_MARKER, 0, index)
    if marker_index < 0 or index - marker_index > 512:
        raise MigrationError(
            "playerdata contains a malformed NBT sequence outside the supported "
            "NeoForge Apotheosis component"
        )

    return raw.replace(_NEOFORGE_BAD_SEQUENCE, _NEOFORGE_FIXED_SEQUENCE, 1)


def _load_compound(path: Path, label: str) -> nbtlib.File:
    try:
        with gzip.open(path, "rb") as source_file:
            raw = source_file.read()
        document = _parse_nbt(raw)
    except Exception as error:
        if label != "playerdata":
            raise MigrationError(
                f"could not read {label} as valid gzip-compressed NBT: {error}"
            ) from error
        try:
            document = _parse_nbt(_repair_known_modded_nbt(raw))
        except MigrationError:
            raise
        except Exception as repair_error:
            raise MigrationError(
                f"could not read {label} as valid gzip-compressed NBT: {repair_error}"
            ) from repair_error

    if not isinstance(document, Compound):
        raise MigrationError(f"{label} must have a compound root tag")
    return document


def _prepare_output(level: nbtlib.File, output: Path, force: bool) -> None:
    if output.exists() and not force:
        raise MigrationError(
            f"output already exists: {output} (use --force to overwrite)"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        level.save(temporary_path, gzipped=True)
        os.replace(temporary_path, output)
    except OSError as error:
        raise MigrationError(f"could not write output {output}: {error}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def migrate(
    playerdata_path: str | Path,
    level_path: str | Path,
    output_path: str | Path,
    *,
    force: bool = False,
) -> None:
    """Replace level.dat's Data.Player children with playerdata root children."""

    playerdata = Path(playerdata_path).expanduser()
    level_path = Path(level_path).expanduser()
    output = Path(output_path).expanduser()

    if output.resolve() in {playerdata.resolve(), level_path.resolve()}:
        raise MigrationError("output must be different from both input files")

    source = _load_compound(playerdata, "playerdata")
    level = _load_compound(level_path, "level.dat")

    data = level.get("Data")
    if not isinstance(data, Compound):
        raise MigrationError("level.dat is missing a compound Data tag")
    if not isinstance(data.get("Player"), Compound):
        raise MigrationError("level.dat is missing a compound Data.Player tag")

    data["Player"] = Compound({name: deepcopy(tag) for name, tag in source.items()})
    _prepare_output(level, output, force)
