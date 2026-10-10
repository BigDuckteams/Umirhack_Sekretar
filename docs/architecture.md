# Architecture decisions

1. **Separate OCR, extraction, retrieval and response.** Errors are attributable and providers replaceable.
2. **Abstain when evidence is missing.** An unsupported fluent answer is worse than a visible limitation.
3. **Citations are typed data.** Stable policy IDs and source quotes can be audited and rendered.
4. **TF-IDF before embeddings.** Start with transparent retrieval; add vector search only when evaluation justifies it.
5. **Do not persist raw uploads.** Uploaded files are processed in memory. OCR text is still personal data and needs retention/access controls in production.
