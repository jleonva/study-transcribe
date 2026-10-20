# Improvements to test next

Research checked 2026-10-19. The current Pix2Text output was accepted globally by the user on this date; the review form was not filled. That acceptance is not a ground-truth dataset or a measured generalization score.

| Priority | Experiment | Success criterion | Status |
|---|---|---|---|
| 1 | Resume keyed by source hash, page, DPI, model revision and generation settings; atomic result writes | Reject stale cache after changing one setting; recover interrupted writes | Proposed; current resume trusts result.json presence |
| 2 | Native text extraction plus local math OCR only in mathematical regions | Less CPU time with unchanged reading order and preserved inline math | Proposed; native text is already retained separately |
| 3 | Fixed corpus with inline math, matrices, aligned equations, diagrams and poor scans | Separate omission recall, symbol errors, structure errors and rendering equivalence | Proposed; existing user approval covers the delivered pilot |
| 4 | GPU/ONNX plus small formula batches on a separate runtime | Lower wall time without OOM or changed output on the same pages | Proposed; no GPU speedup measured |
| 5 | Compare PP-FormulaNet and UniMERNet on difficult formula crops | Better fidelity per second/GB than the accepted baseline | Candidates only; not installed or evaluated here |

Retain Pix2Text as default. Docling was slower on all three measured comparison pages, but concurrent load and cold starts mean those results are not a controlled benchmark. A larger model is not automatically an improvement.

## Primary resources

- [Pix2Text usage](https://github.com/breezedeus/Pix2Text/blob/main/docs/usage.md): supports `mfr_batch_size`; recommends values above one for GPU. This supports a batch experiment, not an assumed speedup.
- [ONNX Runtime CUDA requirements](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html): match CUDA/cuDNN and provider versions in a separate environment before attempting GPU inference.
- [OmniDocBench evaluation](https://github.com/opendatalab/OmniDocBench): annotated formula bounding boxes, text/structure evaluation and CDM-based formula evaluation. Render-equivalent LaTeX can differ as strings, so exact string equality alone is insufficient.
- [PP-FormulaNet plus-M model card](https://huggingface.co/PaddlePaddle/PP-FormulaNet_plus-M): candidate specialized recognizer through PaddleOCR/PP-StructureV3. Check runtime and weight licenses before redistribution.
- [UniMERNet](https://github.com/opendatalab/UniMERNet): specialized formula recognition with real-world test distributions, including different rendering conditions. Candidate for a focused crop benchmark.

Do not download every alternative or replace the validated runtime preemptively. Start with cache correctness and a reproducible fixed-page timing experiment; then test optional acceleration against identical source crops and settings.
