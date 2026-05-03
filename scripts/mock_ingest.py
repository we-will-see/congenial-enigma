from api.db.session import SessionLocal
from services.pipeline_service import create_mock_corpus


def main() -> None:
    with SessionLocal() as db:
        create_mock_corpus(db)
    print("Mock ingestion completed")


if __name__ == "__main__":
    main()
