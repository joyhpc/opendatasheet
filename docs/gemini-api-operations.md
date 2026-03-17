# Gemini API Operations

## Purpose

Most extraction value in this repository comes from Gemini, but most operational instability also starts there. This document defines how to treat Gemini failures as diagnosable infrastructure signals instead of vague model problems.

## Hard Requirements

- `GEMINI_API_KEY` must be set in the environment
- the pipeline should never rely on a hardcoded fallback key
- simple key probes should be separated from full PDF extraction runs

## Failure Classes

### Permission failure

Typical signal:

- `403 PERMISSION_DENIED`
- consumer suspended
- invalid or unauthorized project

Meaning:

- not a prompt issue
- not a PDF issue
- not a timeout issue

Action:

- stop blaming page classification
- validate the key with a minimal probe
- replace or fix the key before resuming

### Network hang or long read

Typical signal:

- call blocks in `httpx` or TLS socket read
- no response headers arrive for a long time

Meaning:

- upstream did not respond in time
- a heavy domain may be hitting the wrong pages or wrong component class

Action:

- inspect which extractor was active
- reduce scope before increasing timeout

### Structured extraction failure

Typical signal:

- API call succeeds but the result is malformed or low quality

Action:

- inspect prompt, page set, and domain boundary
- do not treat it as a key issue

## Safe Probe Pattern

Before launching a large batch, a minimal API probe is cheaper than discovering a dead key after several minutes:

```bash
python - <<'PY'
from google import genai
import os
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
resp = client.models.generate_content(model="gemini-2.5-flash", contents="ping")
print(bool(resp))
PY
```

The exact model can vary, but the probe should stay cheap and deterministic.

## Operational Rules

- distinguish authentication failures from extraction failures immediately
- use absolute file names in logs so stuck domains can be traced
- do not retry a known suspended key inside a long batch
- if a component class does not need a domain, remove that call path instead of hoping retries will save it

## Repository-Specific Lesson

The discrete-device hang investigation showed a common trap:

- a valid key and an invalid routing policy can look similar from the outside

A long-running Gemini call is not proof that the model is required for that part class.
