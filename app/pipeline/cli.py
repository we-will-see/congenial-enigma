import argparse
import asyncio
from datetime import date

from app.db.session import SessionLocal
from app.pipeline.orchestrator import ingest_filings, process_document, seed_companies


def main() -> None:
    parser = argparse.ArgumentParser(description="Enigma document ingestion pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed-companies")
    backfill = sub.add_parser("backfill")
    backfill.add_argument("--from", dest="from_date", required=True)
    backfill.add_argument("--to", dest="to_date", required=True)
    one = sub.add_parser("process-document")
    one.add_argument("document_id", type=int)
    one.add_argument("--no-embed", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.command == "seed-companies":
            print(seed_companies(db))
        elif args.command == "backfill":
            asyncio.run(ingest_filings(db, date.fromisoformat(args.from_date), date.fromisoformat(args.to_date)))
        elif args.command == "process-document":
            process_document(db, args.document_id, embed=not args.no_embed)


if __name__ == "__main__":
    main()
