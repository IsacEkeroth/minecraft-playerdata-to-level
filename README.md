# Minecraft Playerdata to Level

Copy the root tags from a Java Edition `playerdata/<uuid>.dat` file into the
`Data.Player` compound in `level.dat`.

## Usage

Install the project with `uv`:

```sh
uv sync
```

Run the migration with explicit input and output paths:

```sh
uv run minecraft-playerdata-to-level \
	--playerdata world/playerdata/uuid.dat \
	--level world/level.dat \
	--output migrated-level.dat
```

The command requires gzip-compressed NBT files, validates `Data.Player`, and
always writes gzip-compressed NBT. It creates missing output directories and
refuses to overwrite an existing output unless `--force` is supplied. Neither
input file is modified.

This tool recursively merges every root child from the playerdata file into
`Data.Player`. Source values replace destination values when both exist, while
destination-only player fields and nested mod data are preserved. This matters
for partial modded playerdata files: position, dimension, and backpack data
that are absent from the source are retained. It does not perform Minecraft
version conversion or `DataVersion` upgrades.

The loader also supports the malformed Apotheosis text-component encoding
present in the supplied NeoForge 1.21.1 playerdata example. The compatibility
repair is applied only when the exact known sequence occurs once in the
expected `with` list context.

## Tests

```sh
uv run pytest
```
