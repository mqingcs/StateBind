# Dev69 rule-selection stability

The analysis resamples all 69 development source images with replacement while
retaining the six distance/sign cells of each selected image.  Each replicate
reruns the same nine-rule, 95%-precision-constrained selection used by the
paper; held-out labels are never loaded.

- Bootstrap replicates: 20,000
- Original selected rule: `four_only__d4`
- Original rule remains feasible: 92.46%
- Original rule is reselected: 40.49%
- At least one predefined rule is feasible: 92.47%

`selection_frequency.csv` reports each rule's feasibility and selection rate.
`precision_coverage_cloud.csv` contains the complete replicate-by-rule cloud.
