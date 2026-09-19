# Storage layout profiles

Storage layout profiles describe common physical folder conventions without
making them part of Core or the Noark 5 data model.

The selected profile is used by discovery only when the discovered extraction
matches that profile structurally.

## IKAMR standard

For a discovered extraction below:

`<package_root>/content/sip/content`

the profile fills:

- Source root: `<package_root>`
- Source extraction: the discovered extraction
- Work root: `<package_root>`
- Work content: `<package_root>/content`
- Work operations: `<package_root>/repository_operations`
- Storage root: `<package_root>/aip`

One or more levels beneath `content/sip/content` are allowed. This supports
existing structures such as `content/sip/content/content`.

The profile is a convenience policy, not a universal archival rule. Other
repositories can add their own definitions later, or select
`Ingen automatisk utfylling`.
