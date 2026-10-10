# Evaluation plan

Measure separately:
- OCR: character error rate (CER), word error rate (WER), exact transcription.
- Extraction: per-field precision/recall/F1, exact match for dates/numbers, confidence calibration.
- Retrieval: Recall@k and MRR against labelled clause IDs.
- Grounding: citation precision/completeness, unsupported-claim rate, abstention quality.
- Operations: p50/p95 latency, error rate, memory, cost per page.
- Human factors: correction rate and average correction time.

Use MWS-Vision-Bench for external document-vision regression; the case's synthetic documents for extraction; labelled policy questions for retrieval/answer evaluation. Keep template families in one split to avoid leakage.

Suggested release gates (targets, not measured results): no invented citations in tests; 100% abstention on unanswerable policy questions; field F1 >= 0.90 on held-out case data before making accuracy claims; every administrative decision human-reviewed. Publish dataset/model versions and metric implementation.
