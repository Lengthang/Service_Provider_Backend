import asyncio
from db.database import engine, Base
import models  # registers every model on Base.metadata via models/__init__.py


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Tables dropped and recreated.")


if __name__ == "__main__":
    asyncio.run(main())
