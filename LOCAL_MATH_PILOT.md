# Local mathematical OCR pilot

## User validation received 2026-10-19

The user stated that all equations in the delivered pilot were correct despite not completing the HTML form. Record this as **global user acceptance**, not fabricated per-equation entries or a numerical benchmark score. Raw OCR remains unchanged. The earlier "pending review" descriptions below record the state at the time of the initial run; this declaration supersedes that status for the delivered pilot only.

The pilot extracts one complete chapter from each of three locally supplied books. Books and results remain outside this repository. The OCR pipeline uses local CPU inference, not an inference API. The coordinating coding assistant still consumes tokens; this is not a claim of zero total AI-token use.

## Reproduce

Use Python 3.11 in a separate environment. Install PyTorch 2.5.1 and torchvision 0.20.1 from the official CPU wheel index, then `requirements-local-math.txt`. Do not replace the existing CLI environment. RapidOCR and Transformers pins are necessary: RapidOCR 3.10 changed an API imported by cnstd; Transformers 4.44 could not read the MFR 1.5 tokenizer.

Run `python scripts/local_math_batch.py --config path/to/pilot.json --prepare` once with network access to fetch models. Then run the same command without `--prepare` for local inference. Network sockets are denied after model initialization, and Hugging Face is set offline. Completed pages are resumed from `raw/pix2text/pageNNNN/result.json`.

Run `python scripts/build_math_review.py --config path/to/pilot.json` to assemble `chapter.md`, `chapter.json`, and the review HTML. An optional local `vendor` directory containing KaTeX JS/CSS/fonts enables offline mathematical rendering.

## Evaluation boundary

All OCR is uncorrected and pending human review. A model confidence score is not an accuracy metric. Retain source PDF excerpts, source hashes, raw model blocks, coordinates, and page timings. Missing pages must be reported explicitly. The HTML lists detected display formulas in source order; it is not sufficient to measure omitted formulas. A source-selected consecutive sample is needed for omission review.

The text layer is retained separately in JSON, including on scanned documents where it may be damaged. Model-produced Markdown is the principal transcript. Figures remain images; their internal mathematical labels may not be transcribed. Table recognition is disabled in this pilot. No claim of complete fidelity is made before Jorge's review.

## Upstream resources

- https://github.com/breezedeus/Pix2Text (OCR code)
- https://huggingface.co/breezedeus/pix2text-mfr-1.5 (formula recognition)
- https://huggingface.co/breezedeus/pix2text-mfd-1.5 (formula detection)
- https://github.com/docling-project/docling (comparison engine)
- https://huggingface.co/docling-project/CodeFormulaV2 (comparison formula model)

Keep source books, excerpts, model weights, and transcripts out of Git commits. Their presence on a local disk does not grant republication rights.

## Executed pilot, 2026-10-18

All 79 pages completed: Shreve chapter 1 (24 pages, including a blank last page), Boyd chapter 2 (46 pages), Williams chapter 1 (9 pages). Pix2Text detected 78, 148, and 36 display-formula blocks respectively. These are detection counts, not ground truth. All source hashes matched; assembled Markdown image references resolved.

The review panel contains 15 consecutive source-selected equations, (1.1.1) through (1.2.5), with original crops. All 15 have an associated Pix2Text output. Seven also show a Docling comparison. Full chapters and all detected display formulas are available in the same standalone HTML. Raw output remains uncorrected; mathematical fidelity is pending Jorge's review.

Model weights total 1.086 GB; the model directory is about 1.095 GB. The primary run used CPU, 200 dpi, and the MFR default 1024-token generation ceiling. Processing times sum to about 35.5 minutes for all 79 pages. This is measured under concurrent Docling load, not a controlled speed benchmark.

Docling 2.140.0 / CodeFormulaV2 completed one page from each book in 849.5, 334.6, and 460.6 seconds, including initial loading on the first page. Its internal `document_timeout=600` did not bound the enrichment stage; the first page exceeded ten minutes. Do not interpret that setting as a hard wall-clock timeout. Comparison output is available for review; neither engine has a human-verified accuracy score.

Functional tests use jsdom to verify the 15 sample slots, mathematical rendering, filters, notes, localStorage, export, offline assets, and chapter reading. Browser screenshot verification was unavailable. The raw sources and generated books are local artifacts, not repository content.
