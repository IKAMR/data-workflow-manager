# Profile architecture

## Purpose
Data Workflow Manager shall have a generic application core. Domain-specific knowledge shall be supplied by profiles and external definition files.

A profile may represent Noark 5, Noark 4, SIARD, ADDML or another future domain.

## Mandatory rule: `profile.json` is the authoritative entry point
Every profile SHALL have exactly one manifest:

`config/<profile_id>/profile.json`

The manifest is the authoritative and complete entry point for discovering the profile. A developer, automated tool, AI assistant or runtime component shall not need prior knowledge of the profile's internal file layout.

When profile-specific information is needed:
1. locate `config/<profile_id>/profile.json`;
2. read the manifest;
3. follow the paths declared by the manifest;
4. use only the referenced sources and definitions for profile-specific knowledge.

A profile is not considered complete if important knowledge exists in a file that cannot be discovered from `profile.json`.

## Required manifest areas
The manifest shall declare at minimum profile identity, supported versions where relevant, authoritative source registry, capabilities, test/validation definitions, analysis definitions, standards/metadata/code lists/requirements, schemas, views, documentation and legacy/reference sources where relevant.

`config/profile.schema.json` defines the generic manifest contract.

## Separation between generic engine and profile knowledge
The generic engine may implement reusable mechanisms such as file/XML loading, XPath execution, counting, grouping, date ranges, row extraction, numeric statistics, scope traversal, reconciliation, comparison against externally supplied value sets, result storage, logging and progress events.

The generic engine shall not be the authoritative source for domain knowledge.

Profile-specific facts belong under `config/<profile_id>/`, including element and field names, XPath expressions, metadata identifiers, standard/code values, version-specific rules, validation requirements, schemas, source provenance and profile-specific views.

If generic code must be extended to support a profile requirement, the extension should be a reusable mechanism driven by external definitions. New profile facts shall not be hardcoded in the generic engine.

## Provenance
Every normative rule, metadata definition or standard value set should be traceable to a source registered by the profile. The source registry shall distinguish authoritative specification/source, locally developed definition, legacy/reference source, regression reference and inferred/not-yet-verified information.

Rules shall not silently be copied between specification versions. Version equivalence must be verified or explicitly declared.

## Observation, validation and assessment
Profiles should preserve: `observation -> normative reference -> comparison -> assessment -> report`.

Observed data must be retained even when it differs from a standard value set. A non-standard observed value is not automatically a technical failure unless a separate validated rule explicitly makes it so.

## Completeness and discoverability test
A profile should have automated tests that verify `profile.json` exists, required keys exist, every referenced local path exists, no authoritative profile definition is orphaned outside the manifest, standard/requirement definitions refer to registered sources, and generic code does not contain known profile-specific code values.

## Metadata and requirement registries

A complete profile should expose machine-readable metadata and requirement registries through `profile.json`.

The metadata registry identifies known metadata elements, their source and verification status. It must not invent datatype, occurrence, placement or semantics that have not been source-verified.

The requirement registry contains only normative requirements explicitly verified against an authoritative source. Empty or partial registries are valid when their status is explicit; silently inferred rules are not.

This allows profiles to grow incrementally without confusing implementation history with normative specification.

## Profile knowledge completeness

Each profile should expose a machine-readable statement of knowledge coverage and provenance policy from its `profile.json`.

This prevents partial implementation from being mistaken for complete domain knowledge. A profile may be incomplete, but incompleteness must be explicit and discoverable.

For normative profiles, the preferred lifecycle is:

`authoritative source -> registered source -> verified fact -> profile definition -> generic execution mechanism`

Historical implementation files and regression definitions may be referenced by the profile, but they shall not silently become normative authority.
