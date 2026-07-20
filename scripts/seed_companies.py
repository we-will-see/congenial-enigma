from app.db.session import SessionLocal
from app.pipeline.orchestrator import seed_companies
from app.pipeline.universe import TARGET_COMPANIES


def main() -> None:
    with SessionLocal() as db:
        seed_companies(db)
    print(f"Seeded {len(TARGET_COMPANIES)} companies")


if __name__ == "__main__":
    main()
