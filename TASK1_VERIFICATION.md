# Composition and batch review verification

## Changes

- Composition builds a pool from the selected vocabulary and tile silhouette.
  It draws 16 rows using the seed, with a cap of 12 rows per layout and storage
  type when multiple types are available. Within a type it favours combinations
  used fewer times. The UI keeps the vocabulary, seed and high/low controls.
- High means the tallest geometry reaches 0.42 tile units above the slab. Tall
  shed and short silo variants are stored as data. Hall width and length still
  fit the predetermined plan dimensions. The former height and width draws,
  diversity control, storage filter and height-comparison mode were removed.
- Placement checks use authored footprints. The annex intentionally overlaps
  its host wall. The corner storage centres were widened to clear neighbouring
  tank footprints. Pipe ties connect adjacent vessels at their stored port
  elevation.
- Reroll renders one row and keeps the same row number. Its seed inputs are
  the batch seed, row number and revision. The 15 other rows retain their
  original files and URLs.

## Checks

- All 171 tests passed, including the existing indexed-pixel, palette and
  frozen-mesh goldens.
- Every eligible installed composition was compiled and checked for tile
  bounds. The placement tests also reject intersecting storage footprints.
- The HTTP integration check compared the unaffected rows, inspected all
  exported PNGs and reproduced the rerolled row's four PNGs byte-for-byte
  from the exported scene.
- UI interaction checks covered the 16-row sheet, 100% and 400% zoom,
  selection, both reroll controls and copy/save actions in a simulated DOM.
  This environment prevented Chromium from launching, so native clipboard
  permissions and browser download behaviour remain unverified.
- Four sample batches were rendered and inspected across all angles. The
  high/low distinction is visible, and the rear angles can still hide low
  tanks or parts of an annex. These are manual visual checks.

## Catalogue diversity

Across seeds 0–29, the 16-row batches contained the following numbers of
distinct composition IDs. A distinct ID can still look similar at 100%.

| Vocabulary | Low | High |
| --- | ---: | ---: |
| Grain handling | 9–13 | 10–16 |
| Liquid storage | 7–12 | 7–12 |
| Both | 10–16 | 11–16 |

Liquid storage has 12 eligible compositions for each silhouette. The cap
permits skew and cannot supply designs beyond the eligible pool.
