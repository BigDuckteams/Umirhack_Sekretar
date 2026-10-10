"""OCR-only baseline for MWS-Vision-Bench; not the official overall score."""
import argparse
import json
from pathlib import Path
import re
import sys

def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()

def main() -> int:
    try:
        from datasets import load_dataset
        from jiwer import cer
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        print("Install optional dependencies: pip install -e '.[benchmark]'. " + str(exc), file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="default", choices=["default", "en", "zh"])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output", type=Path, default=Path("artifacts/mws_ocr_baseline.jsonl"))
    parser.add_argument("--lang", default="rus+eng")
    args = parser.parse_args()
    dataset = load_dataset("MTSAIR/MWS-Vision-Bench", args.config, split="train")
    if args.limit:
        dataset = dataset.select(range(min(args.limit, len(dataset))))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    seen, evaluated, scores = 0, 0, []
    with args.output.open("w", encoding="utf-8") as out:
        for item in dataset:
            task = str(item.get("type", ""))
            prediction, error = "", None
            if "full-page OCR" in task:
                try:
                    image = item.get("image")
                    if isinstance(image, dict) and image.get("bytes"):
                        from io import BytesIO
                        image = Image.open(BytesIO(image["bytes"]))
                    if image is not None:
                        prediction = pytesseract.image_to_string(image, lang=args.lang).strip()
                        refs = item.get("answers") or []
                        if refs:
                            scores.append(cer(normalize(str(refs[0])), normalize(prediction)))
                        evaluated += 1
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
            out.write(json.dumps({"id": str(item.get("id", seen)), "type": task, "prediction": prediction, "error": error}, ensure_ascii=False) + "\n")
            seen += 1
    print(json.dumps({"dataset": "MTSAIR/MWS-Vision-Bench", "config": args.config,
                      "rows_seen": seen, "ocr_rows_evaluated": evaluated,
                      "mean_character_error_rate": sum(scores) / len(scores) if scores else None,
                      "output": str(args.output), "note": "OCR-only baseline; not the official benchmark score."}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
