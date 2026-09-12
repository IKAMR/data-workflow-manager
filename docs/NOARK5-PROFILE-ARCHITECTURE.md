# Noark 5 profile architecture

## Entry point
The authoritative entry point for Noark 5-specific knowledge is `config/noark5/profile.json`. Anyone implementing, validating, analysing or documenting Noark 5 support should start there and follow the referenced definitions.

## Knowledge layers
### Sources
`config/noark5/standards/sources.json` registers authoritative Noark documentation, version-specific metadata catalogues and legacy/reference material.

### Standards and metadata
`config/noark5/standards/` contains machine-readable Noark-specific metadata, standard values and later requirement registries. Version-specific information must be explicit. A value or rule verified for one version shall not automatically be copied to another version.

### Tests and analyses
`config/noark5/tests/` and `config/noark5/analysis/` contain XPath/test definitions and reusable analysis definitions. These describe what to analyse; the Python engine provides generic mechanisms.

### Structural/schema validation
The manifest references Noark-specific XML/schema validation configuration separately from the generic execution engine.

### Views and reporting
Views consume canonical results and shall not become duplicate analysis engines. Historical U1/U2 views are migration/regression references, not a general Noark naming standard.

## U1/U2 terminology
`U1` and `U2` are local historical names used in IKAMR's KDRS Query definition files. They are not established Noark 5 terminology and are not an official KDRS naming standard. They may remain where historical traceability or regression requires them. New architecture should use functional names.

## Authoritative hierarchy
1. official Noark specification and appendices registered in `sources.json`;
2. machine-readable definitions under `config/noark5/`;
3. tests and analysis definitions consuming those definitions;
4. historical KDRS Query material as traceability/regression reference;
5. generic Python engine as execution mechanism, not Noark authority.

If a legacy test and an authoritative Noark source disagree, the disagreement must be documented. Legacy behaviour must not silently become the Noark rule.

## Current and future registries
Current material includes standard value sets, XPath test definitions, analysis/coverage definitions and schema validation configuration. Planned registries include metadata definitions per Noark version, normative requirement/rule definitions per Noark version, reusable functional views and external comparison definitions for archive creator control data.

## Validation model
A. Noark 5 specification versus Noark 5 extract.
B. Noark 5 extract versus its own content and internal consistency.
C. Noark 5 extract versus archive creator control/reference data.

Area C is a comparison layer above canonical extract results and shall not be embedded as Noark XPath logic.

## Responsibility and reporting
The archive creator remains responsible for the content of the extract. The depot performs pragmatic validation and documents deviations. A new extract is normally required only for serious structural or content deficiencies. Reports should present evidence in a form the archive creator can read and accept, without turning the report layer into a second analysis implementation.

## Machine-readable metadata and requirements

The Noark 5 profile exposes:

- `config/noark5/standards/metadata/index.json`
- `config/noark5/standards/requirements/index.json`

Metadata files are version-specific and currently contain only identifiers and standard-value relationships already verified in the official metadata catalogues. Datatype, cardinality and structural placement shall be added only after explicit verification.

Requirement files are deliberately created empty with status `not_yet_populated` until the corresponding normative requirements have been reviewed in the official Noark specification. Legacy XPath tests do not become normative requirements merely by existing.

## Specification knowledge lifecycle

Noark 5 knowledge is promoted into the profile through a controlled lifecycle:

`official source -> source registration -> explicit verification -> machine-readable fact -> test/analysis use -> result/evidence`

Two machine-readable control files support this:

- `config/noark5/standards/specification_coverage.json`
- `config/noark5/standards/provenance_contract.json`

The coverage file states what parts of the specification have actually been represented and what is still not claimed. The provenance contract states what source information a normative fact must carry.

This is intentionally conservative. An empty requirement registry is more correct than a populated registry based on assumptions. Likewise, metadata properties such as datatype, cardinality and structural placement remain unclaimed until they have been explicitly verified.

The historical KDRS Query material remains useful for regression and migration traceability, but it does not count as normative specification coverage.


## a23 – first verified normative facts

a23 demonstrates the complete provenance path with selected official Noark 5 v5.0 facts. The v5 metadata registry now contains a fully source-verified M001 `systemID` entry. The v5 requirement registry contains two explicitly verified functional requirements concerning creation and closure of classes. These are marked as not directly testable from a static extract because they describe system behaviour. a23 does not claim full transcription of the Noark 5 specification; `specification_coverage.json` remains authoritative for coverage.

## Execution profiles

The Noark 5 test catalogue declares `normal` and `regression` execution profiles. The normal profile excludes tests whose lifecycle role is `development_regression_reference`. Regression execution retains them for controlled historical comparison.

Execution-profile semantics are definition-driven and do not hardcode U01/U02 identifiers in the generic engine.
