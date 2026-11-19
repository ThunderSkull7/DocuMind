# Real-World Evaluation Protocol

## Current evidence boundary

The checked-in benchmark uses 50 synthetic invoices. Its extraction scores and latency figures describe those fixtures only. They do not establish accuracy on invoices from external vendors, real business processes, or future production traffic.

No real-invoice evaluation was performed for this protocol. Do not report one until a permissioned corpus has been assembled and evaluated.

## Corpus requirements

Before collecting documents:

- Obtain documented permission for evaluation use and define retention and deletion dates.
- Restrict access to the evaluation team. Remove or replace personal and account identifiers where this does not invalidate the field being evaluated.
- Record source, document type, digital versus scanned status, scan quality, language, currency, and template/vendor group without exposing confidential invoice contents in reports.
- Sample across unrelated vendors and templates. Keep entire vendor/template groups out of development when measuring generalization; do not split near-identical invoices across development and holdout sets.
- Keep the holdout set locked until extraction rules and thresholds are frozen.

## Ground truth

Annotate header fields, line items, totals, and evidence boxes against the source PDF. Mark unreadable, absent, and genuinely ambiguous values separately; do not force a single label where the document itself is ambiguous. Use independent annotations with adjudication for disagreements, and retain annotation provenance.

## Reported measures

Report counts and denominators by digital/scanned status, scan quality, language, and vendor/template group:

- Field-level exact match and normalized exact match, with precision, recall, and F1.
- Numeric and date normalization accuracy, including ambiguous and missing-field handling.
- Line-item detection and field accuracy separately from invoice-level totals.
- Evidence-box overlap (for example, intersection over union) and invalid/out-of-page box rate.
- Routing accuracy, processing latency, and failure rate by document type.

Separate raw extraction performance from reviewer-corrected outcomes. Report confidence intervals where the sample size supports them, and include failures rather than excluding difficult documents.

## Release gate

Publish the corpus description, annotation policy, evaluation script version, and results only when permission allows. State the tested population and known gaps. Keep the current synthetic benchmark labeled as synthetic; do not replace it with real documents in the public repository.
