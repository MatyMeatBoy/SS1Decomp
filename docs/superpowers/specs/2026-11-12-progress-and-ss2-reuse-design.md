# SS1 progress and SS2 reuse

The owner requested a fork named `MatyMeatBoy/SS1Decomp`, the same progress
presentation as SS2Decomp, and an investigation of reusable SS2 code that can
accelerate matching C in SS1. emmkay440 explicitly permitted the fork in SS2
issue79. Preserve his history and attribution; author new work as MatyMeatBoy.

## Approach

Adapt SS2's badge and byte-weighted SVG rendering, using SS1's own linker,
symbols and compiler configuration. Keep SS1's existing `make progress` and
`--json` interface. A separate metadata-only build can compile and link code
without a ROM by replacing only the cartridge-header and opaque-data incbins
with equal-sized zero storage in isolated build inputs. It must never create a
ROM, write normal build objects, or claim the ROM matches.

This is preferable to publishing stale historical CSV percentages or guessing
function sizes from source declarations. A full port of SS2's many unrelated
regional/data tools would introduce assumptions SS1 cannot currently prove.

## Metrics and presentation

Show code, names and data separately, as on SS2. Function area means attributed
linked code bytes, including its pools/alignment. Names do not earn matching
credit; raw preserved data does not imply identified formats. Exclude cartridge
header bytes from executable-code totals and deduplicate aliases by address.
Library classification follows linked object ownership, including MultiSio.
Original hand-written assembly is explicitly separate from unfinished ASM.

ROM verification is a separate status. Only an actual `make compare` against
the owner's SHA1-verified USA AHUE ROM can claim an exact ROM match. Metadata
builds and cross-game similarities must never set that status to true.

## SS2 reuse

Preserve a pinned candidate manifest with SS1/SS2 addresses, source paths,
structural similarities, known game-specific differences and byte impact.
Start with existing near-match drafts when available. Similarity is a research
lead, not proof. Adapt game-specific layouts and constants, compare compiled
instructions, then run the complete SS1 ROM check before credit or integration.

## Validation

Test metadata input guards, object-path isolation, inventory partitions, alias
deduplication and rendering output. Compare metadata-derived inventory with the
real map/ELF when the ROM is supplied. Run the ordinary ROM gate before
committing source changes. Never stage ROMs, generated objects or scratch work.
