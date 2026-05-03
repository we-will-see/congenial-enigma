from sqlalchemy import select

from api.db.models import Company
from api.db.session import SessionLocal
from services.companies import MVP_COMPANIES


def main() -> None:
    with SessionLocal() as db:
        for scrip_code, name, sector in MVP_COMPANIES:
            company = db.scalar(select(Company).where(Company.scrip_code == scrip_code))
            if company:
                company.name = name
                company.sector = sector
            else:
                db.add(Company(scrip_code=scrip_code, name=name, sector=sector, active=True))
        db.commit()
    print(f"Seeded {len(MVP_COMPANIES)} companies")


if __name__ == "__main__":
    main()
