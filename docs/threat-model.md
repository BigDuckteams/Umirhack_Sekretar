# Initial threat model

| Threat | Baseline mitigation | Required before production |
|---|---|---|
| Oversized/malformed upload | size limit, signature check, decoder errors | proxy limits, malware scan, isolated worker |
| Instructions embedded in document | no LLM in baseline | treat document text as untrusted if LLM is added |
| PII in logs | log IDs and lengths only | redaction, access control, retention |
| OCR/extraction error | evidence/confidence and review flag | validation metrics and correction UI |
| Stale policy | stable clause IDs | policy versions, effective dates, approvals |
| Unauthorized access | prototype is local-only | SSO/OIDC, RBAC, rate limiting |
| Citation hallucination | citations built from retrieved clauses | regression suite and release gates |
