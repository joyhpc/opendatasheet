# Batch Processing Runbook

## Scope

This runbook is for `batch_all.py`, which processes canonical raw datasheets under `data/raw/datasheet_PDF/` and writes structured output into `data/extracted_v2/`.

## Normal Workflow

### Inspect the candidate set

```bash
python3 batch_all.py --dry-run
python3 batch_all.py --subdir Transistor --dry-run
```

Use `--dry-run` first when:

- a corpus was recently imported
- many files were deleted
- a new routing rule was added

### Run a small sample

```bash
python3 batch_all.py --subdir Transistor --limit 3
```

Do this before a full corpus run if:

- prompts changed
- extractor order changed
- a new fast path was added

### Run the full batch

```bash
python3 batch_all.py --subdir Transistor
```

## What Success Means

A successful batch is not “zero failed files at any cost”. It means:

- valid files were processed
- clearly invalid files were surfaced as failures
- the batch kept progressing
- logs are specific enough to separate source corruption from extraction defects

## Output Expectations

- structured results go to `data/extracted_v2/`
- batch summary goes to `data/extracted_v2/_batch_all_summary.json`
- failures are listed at the end with file name and short reason

## Operational Tips

- keep `PYTHONUNBUFFERED=1` when capturing live logs
- redirect logs to a temp file for long runs
- inspect the first few files before leaving a long batch unattended
- count generated JSON files only after confirming the target output directory

## When To Stop A Batch

Stop only if:

- the same structural error repeats across many healthy-looking files
- the key is invalid and no files can proceed
- runtime blows up after a routing or registry change

Do not stop a batch only because a few source PDFs are corrupt. That is a data-quality issue, not a pipeline-stability issue.
