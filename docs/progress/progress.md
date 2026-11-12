# Shining Soul progress

ROM match: **not verified**.

Linked source coverage; function spans include literal pools/alignment. Aliases are deduplicated by address. Cartridge header bytes are excluded.

| Partition | C bytes / code bytes | C functions / functions | Existing names |
|---|---:|---:|---:|
| Game | 148,040 / 325,204 (45.522%) | 866 / 976 | 175 / 976 |
| SDK libraries | 6,376 / 12,684 (50.268%) | 64 / 166 | 151 / 166 |
| All code | 154,416 / 337,888 (45.700%) | 930 / 1142 | 326 / 1142 |

Opaque data preserved: 8,050,532 bytes. Identified formats: 0 bytes (0%).

Green cells mean linked C source coverage. Existing names do not establish semantics. Original assembly is separate from pending assembly.

Generated from the linked ELF/map. Metadata-only output cannot establish an exact ROM match.
