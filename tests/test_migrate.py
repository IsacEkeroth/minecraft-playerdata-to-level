from __future__ import annotations

import gzip
from pathlib import Path

import nbtlib
import pytest
from nbtlib import Compound, File, Int, String

from minecraft_playerdata_to_level.migrate import (
    MigrationError,
    _load_compound,
    migrate,
)


def write_nbt(path: Path, root: Compound) -> None:
    File(root).save(path, gzipped=True)


def read_nbt(path: Path) -> File:
    return nbtlib.load(path, gzipped=True)


@pytest.fixture
def nbt_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    playerdata_path = tmp_path / "player.dat"
    level_path = tmp_path / "level.dat"
    output_path = tmp_path / "out" / "level.dat"

    write_nbt(
        playerdata_path,
        Compound(
            {
                "DataVersion": Int(4189),
                "Health": String("20"),
                "Nested": Compound({"Value": String("from-playerdata")}),
            }
        ),
    )
    write_nbt(
        level_path,
        Compound(
            {
                "Data": Compound(
                    {
                        "LevelName": String("Test World"),
                        "Player": Compound(
                            {
                                "OldOnly": String("remove me"),
                                "Health": String("old value"),
                            }
                        ),
                    }
                ),
                "Unrelated": String("preserve me"),
            }
        ),
    )
    return playerdata_path, level_path, output_path


def test_migrate_replaces_player_and_preserves_unrelated_tags(
    nbt_files: tuple[Path, Path, Path],
) -> None:
    playerdata_path, level_path, output_path = nbt_files
    original_playerdata = playerdata_path.read_bytes()
    original_level = level_path.read_bytes()

    migrate(playerdata_path, level_path, output_path)

    result = read_nbt(output_path)
    player = result["Data"]["Player"]
    assert set(player) == {"OldOnly", "DataVersion", "Health", "Nested"}
    assert player["OldOnly"] == "remove me"
    assert player["Nested"]["Value"] == "from-playerdata"
    assert result["Data"]["LevelName"] == "Test World"
    assert result["Unrelated"] == "preserve me"
    assert playerdata_path.read_bytes() == original_playerdata
    assert level_path.read_bytes() == original_level
    with gzip.open(output_path, "rb") as output_file:
        assert output_file.read(1) == b"\x0a"


def test_existing_output_requires_force(nbt_files: tuple[Path, Path, Path]) -> None:
    playerdata_path, level_path, output_path = nbt_files
    output_path.parent.mkdir()
    output_path.write_bytes(b"keep me")

    with pytest.raises(MigrationError, match="already exists"):
        migrate(playerdata_path, level_path, output_path)
    assert output_path.read_bytes() == b"keep me"

    migrate(playerdata_path, level_path, output_path, force=True)
    assert read_nbt(output_path)["Data"]["Player"]["Health"] == "20"


@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        ("missing_data", "compound Data"),
        ("missing_player", "compound Data.Player"),
    ],
)
def test_required_level_structure_is_validated(
    tmp_path: Path, fixture: str, message: str
) -> None:
    playerdata_path = tmp_path / "player.dat"
    level_path = tmp_path / "level.dat"
    write_nbt(playerdata_path, Compound({"Health": String("20")}))
    level_root = (
        Compound({}) if fixture == "missing_data" else Compound({"Data": Compound({})})
    )
    write_nbt(level_path, level_root)

    with pytest.raises(MigrationError, match=message):
        migrate(playerdata_path, level_path, tmp_path / "out.dat")


def test_output_cannot_be_an_input(nbt_files: tuple[Path, Path, Path]) -> None:
    playerdata_path, level_path, _ = nbt_files

    with pytest.raises(MigrationError, match="different"):
        migrate(playerdata_path, level_path, level_path)


def test_malformed_playerdata_is_reported(tmp_path: Path) -> None:
    playerdata_path = tmp_path / "player.dat"
    level_path = tmp_path / "level.dat"
    playerdata_path.write_bytes(b"not nbt")
    write_nbt(
        level_path,
        Compound({"Data": Compound({"Player": Compound({})})}),
    )

    with pytest.raises(MigrationError, match="valid gzip-compressed NBT"):
        migrate(playerdata_path, level_path, tmp_path / "out.dat")


def test_migrates_supplied_modded_examples(tmp_path: Path) -> None:
    project_root = Path(__file__).parents[1]
    playerdata_path = (
        project_root / "example_files" / "8be892fe-8011-4c27-830b-6c1911bdc6fc.dat"
    )
    level_path = project_root / "example_files" / "level.dat"
    output_path = tmp_path / "migrated-level.dat"

    migrate(playerdata_path, level_path, output_path)

    source = _load_compound(playerdata_path, "playerdata")
    result = read_nbt(output_path)
    player = result["Data"]["Player"]
    assert set(source).issubset(player)
    assert "Pos" in player
    assert "Dimension" in player
    assert "toolbelt:belt" in player["neoforge:attachments"]
