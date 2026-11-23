# Future design – Jobs, batches and data flow

This document collects design ideas and requirements for future development of
Noark 5 Workflow Manager.

The purpose is to document the intended direction before all details have been
implemented or decided. The document is therefore not a description of the
current implementation.

The same principles should, where appropriate, be reusable in SIARD Workflow
Manager and other tools in the preservation workflow.

## 1. Persistent jobs and run files

Jobs and job lists should be persistent.

It should be possible to save the current working state to an external,
versioned run/project file, close the application, reopen it later and continue
the work.

A run file should be able to represent:

- job ID and name
- source location
- output location
- workflow and operation order
- operation-specific parameters
- metadata used by operations
- job status
- workflow state
- references to logs and results
- creation and modification timestamps
- application and file-format version

Large archival objects must not be embedded in the run file. Sources and
outputs should normally be referenced by location.

A job should also be possible to put aside while other jobs are processed, and
then reopen and continue later.

A basic principle remains:

> One job = one source + one workflow + one output area.

## 2. Batch results and reporting

A job list or batch should have a common result/report in addition to the
individual results and provenance documentation for each job.

The common report should not be stored inside an arbitrary job's output area.

The user should be able to select a separate report area. This allows the
individual job outputs to be placed freely according to operational and
preservation requirements.

A batch report should at minimum be able to record:

- batch/run identification
- job ID and name
- source
- output
- workflow
- status
- start and finish time
- errors and warnings
- references to detailed logs and results

The reporting model should later be extendable with results from native Noark 5
analysis, Arkade 5 and other validation or preservation operations.

## 3. Discovery of job candidates

Jobs should eventually be possible to create automatically by discovering
candidate sources in a directory structure.

Discovery should be configurable using, for example:

- a root directory from which discovery starts
- directory or file name patterns
- regular expressions
- required files
- required subdirectories
- structural characteristics
- other configurable rules

A possible processing model is:

    Root
      |
      v
    Discovery
      |
      v
    Candidate
      |
      v
    Prequalification
      |
      +---- rejected
      |
      v
    Accepted candidate
      |
      v
    Job

Discovery should be kept separate from execution. Discovering a large archival
object must not by itself cause the object to be copied, unpacked or hashed.

## 4. Prequalification

A discovered candidate may need to satisfy additional requirements before a job
is created.

Prequalification should not be tied to one fixed implementation.

It should eventually be possible to use:

- built-in rules
- configurable rules
- Python-based checks
- external analysis tools
- combinations of several checks

Existing experience with Python scripts for prequalifying job candidates can be
used as input when designing this interface.

The architecture should also leave room for future AI-assisted analysis.

For sensitive archival material, such functionality must not require data to be
sent to external AI services. Local processing, including local language models
such as Ollama or equivalent technology, may therefore be relevant in the
future.

AI should be considered an optional analysis component, not a requirement for
the job model.

## 5. Automatic generation of output areas

For accepted candidates, Workflow Manager should be able to generate suitable
output directories automatically.

The user may, for example, select one output root and define rules for generating
one output area per accepted candidate.

Example:

    Sources/
      extraction-A/
      extraction-B/
      extraction-C/

                |
                v

    JOB-001 -> extraction-A -> Results/extraction-A/
    JOB-002 -> extraction-B -> Results/extraction-B/
    JOB-003 -> extraction-C -> Results/extraction-C/

Naming should eventually be configurable and may use source information,
metadata or other rules.

Automatic output generation must not remove the existing ability to select an
individual output area for each job.

## 6. Metadata import and reuse

Job configuration should support automatic use of metadata from other sources.

An existing `info.xml` is one important example, but the model should not be
limited to this format.

A possible metadata flow is:

    defaults
       |
       v
    metadata discovered with source
       |
       v
    imported metadata (for example info.xml)
       |
       v
    batch/job rules
       |
       v
    manual review and editing

Where practical, the provenance of metadata values should be retained so that
it is possible to determine where important preservation metadata originated.

## 7. Editing jobs and metadata

A persistent job must be possible to reopen and edit.

This may include:

- source and output configuration
- workflow
- operations
- operation parameters
- metadata
- other job configuration

A distinction must be maintained between editable job configuration and
documentation of events that have already occurred.

Completed preservation events should not simply be rewritten as if the original
event never happened. Where provenance requires it, later corrections or
changes should instead be represented as subsequent actions.

This distinction is particularly important for PREMIS and other preservation
documentation.

## 8. Stepwise workflow execution and checkpoints

A job must not require the entire workflow to execute from beginning to end in
one uninterrupted run.

Real preservation work contains natural checkpoints where automated processing
must stop for inspection, assessment or manual work.

For example:

    Receipt
      |
    Unpacking
      |
    CHECKPOINT -> inspection / manual processing
      |
    Analysis
      |
    CHECKPOINT -> assessment
      |
    Validation
      |
    CHECKPOINT -> correction / decision
      |
    Packaging
      |
    Verification
      |
    Finalisation

The persistent job model should therefore eventually be able to represent the
state of the workflow, including which operations have completed and where
processing can continue.

A future scheduler should be able to support concepts such as:

- run complete job
- run selected jobs
- run next operation
- run selected operations
- continue from checkpoint
- pause a job
- resume a job

This is important because automation must coexist with professional archival
assessment and manual preservation work.

## 9. External preservation/CRM system integration

Workflow Manager should be designed as one component in a larger information
flow rather than as an isolated application.

A separate database/CRM solution is being developed for communication and
status sharing with archive creators/owner municipalities. Access is intended
to use Entra ID.

This creates an opportunity to establish a common information flow before an
archival transfer reaches Workflow Manager.

Archive creators should eventually be able to register and quality-assure
relevant metadata through a suitable frontend. Metadata collected during this
process should then be reusable throughout the preservation workflow instead of
being manually registered again in each system.

A conceptual flow may be:

    Archive creator / municipality
              |
              v
    Registration and metadata QA
              |
              v
        CRM / database
              |
              v
       Workflow Manager
              |
              v
    Analysis / validation /
    preservation processing
              |
              v
        CRM / database
              |
              v
    Updated status, metadata
    and processing results

The integration must therefore support data flow in both directions.

### 9.1 Data into Workflow Manager

Workflow Manager should eventually be able to receive or retrieve information
such as:

- transfer/archive identification
- archive creator
- system information
- contact/context information
- expected content
- preservation metadata
- source locations or references
- previously quality-assured metadata
- processing requirements
- status information

This information should be reusable when creating jobs and configuring
operations.

The objective is to avoid repeated manual entry of metadata that has already
been collected and quality-assured earlier in the process.

### 9.2 Data from Workflow Manager

Workflow Manager should likewise be able to return relevant information after
or during processing.

Examples may include:

- job status
- workflow status
- validation status
- warnings and errors
- processing timestamps
- package identifiers
- preservation status
- selected metadata corrections or enrichments
- references to reports
- completion information

The CRM/database can then provide archive creators and internal users with an
updated view of the transfer without requiring direct access to Workflow
Manager.

### 9.3 Integration principles

The integration should be based on a defined interface rather than direct
coupling between the internal data structures of the applications.

Conceptually:

    External system
          |
       Adapter/API
          |
    Common data model
          |
    Job / Workflow Manager

This should make it possible to change either application without requiring the
other to use the same internal database or implementation.

The integration model should consider:

- stable identifiers
- versioned data structures/API contracts
- authentication and authorisation
- metadata provenance
- timestamps
- source of each update
- validation of incoming data
- conflict handling
- auditability
- separation between status information and preservation documentation

Entra ID authentication belongs primarily to the external service/interface
boundary and should not become a requirement of the core Job/Workflow model.

## 10. Shared use with SIARD Workflow Manager

These concepts should not unnecessarily be made Noark 5-specific.

In particular, the following are potential shared concepts:

- Job
- Batch
- persistent run/project files
- workflow state and checkpoints
- discovery
- prequalification
- output generation
- metadata provenance
- external-system integration
- scheduler
- worker
- reporting

Domain-specific functionality should remain behind adapters or operations where
appropriate.

This makes it possible for Noark 5 Workflow Manager and SIARD Workflow Manager
to participate in the same overall preservation methodology while retaining
their domain-specific processing.

## 11. Long-term conceptual model

The direction described in this document can be summarised as:

    External registration / CRM
                 |
                 v
          Metadata / status
                 |
                 v
    Discovery -> Prequalification
                 |
                 v
             Project
                 |
               Batch
                 |
          +------+------+
          |             |
         Job           Job
          |             |
       Workflow      Workflow
          |             |
      Operations    Operations
          |             |
      Checkpoints   Checkpoints
          |             |
       Results       Results
          +------+------+
                 |
                 v
          Batch report
                 |
                 v
       Status / metadata
                 |
                 v
       External CRM/system

This is a future design direction, not a statement that all components are
currently implemented.