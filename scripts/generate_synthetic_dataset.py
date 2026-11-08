"""Command-line utility to generate the DocuMind synthetic invoice corpus."""

import argparse
from pathlib import Path

from documind.dataset.generator import SyntheticInvoiceGenerator


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate deterministic synthetic invoice corpus for DocuMind."
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to save generated PDFs (default: data/synthetic_documents)",
    )
    parser.add_argument(
        "--annotations-dir",
        type=Path,
        default=None,
        help="Directory to save JSON annotations (default: data/annotations)",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="Path for manifest JSON (default: data/manifest.json)",
    )

    args = parser.parse_args()

    generator = SyntheticInvoiceGenerator(
        seed=args.seed,
        output_dir=args.output_dir,
        annotations_dir=args.annotations_dir,
        manifest_path=args.manifest_path,
    )
    manifest = generator.generate_corpus()
    print(f"Generated {manifest.total_documents} documents.")
    print(f"Digital text invoices: {manifest.digital_count}")
    print(f"Scanned image invoices: {manifest.scanned_count}")
    print(f"Manifest written to: {generator.manifest_path}")


if __name__ == "__main__":
    main()
