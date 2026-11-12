# Regional builds and language preservation

## Independent profiles

Europe is the default for `make`, `make compare`, `make progress` and the public
progress views. USA is a separate reference under `docs/progress/usa/` and
`REGION=us`; percentages are never combined.

| Profile | Game code | Original SHA1 | Current verification |
|---|---|---|---|
| USA | AHUE | `14723ead8634959b4fad027d9618c0860b82ea67` | Preserved upstream sources; the local owner supplied Europe, so this continuation does not claim a new USA full-ROM check. |
| Europe | AHUP | `6e80a65cca65236e405940c880b144d77f3f4f08` | Full 8 MiB byte comparison and SHA1 match; see the current source receipt. |

The first verified cohort covers 137,224 / 338,548 executable bytes. The 188-byte cartridge
header is excluded. The remaining 201,324 code bytes stay pending raw spans.
The 8,049,872-byte asset region is preserved, not credited as identified formats.
Do not add USA and Europe percentages or call raw preservation decompilation.

## Why Europe is a separate build

The European dump is not the USA ROM with a different header. Compared with
the preserved USA source layout, it has multiple code shifts and actual changes
in language and UI routines. A single address delta is invalid. In particular,
European armor/head names use 32-byte slots where the USA item-name path uses
40 bytes. Blindly substituting the USA data or structs would be incorrect.

The EU boot routine at `0x08001FD0` offers five choices and assigns language IDs
through the table at `0x080FADE4`. The existing USA source initializes language1
but still contains multilingual code paths and record layouts; that alone does
not prove either presence or absence of every localized USA asset.

This project preserves the European English/French/German/Italian/Spanish
release, including the original selector. It does not publish game text or
claim a new translation. Exact full-ROM reproduction establishes that the
original multilingual bytes are unchanged.

## Shared C proof

`eu_module_match.py` accepts only unique complete module matches with supported
ELF relocations. It keeps non-relocation instructions/constants fixed and derives
external bindings from actual EU sites. Different source/header/compiler/object
inputs or ambiguous matches cannot silently earn credit.

`eu_build.py` independently checks provenance, snapshots the verified objects,
links them at EU addresses and verifies every complete linked C span. All gaps
come from the owner's original ROM. The complete output must equal the input
byte for byte and match the fixed AHUP SHA1 before a receipt is written. A raw
fallback is a pending span, not a named function or completed assembly source.

The source receipt uses LF-normalized SHA256 text fingerprints so Git's Windows
CRLF checkout does not create false staleness on Linux. Compiler/object hashes
and the original manifest digest remain raw binary provenance. A semantic source
change invalidates the receipt. CI presents this recorded owner-local check;
it never downloads or uploads a ROM.

## Commands

```sh
make compare-eu
make record-eu
make progress-map
```

Supply the EU ROM as `baserom_eu.gba`, or pass `EU_ROM=/path/to/owned.gba`.
`compare-eu` builds under `build/metadata/` and `build/eu/`; ordinary USA objects
and source files remain untouched. `record-eu` additionally copies only the
successful JSON receipt into `config/regions/eu_verified.json`.

For USA, retain `baserom.gba` and use `make REGION=us compare` (or `make compare-us`). Never change
its expected SHA1 to accommodate a different region. New EU-specific source
variants must preserve the USA source base and pass their affected regional
build gates.
