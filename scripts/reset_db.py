import os
import sys
import asyncio

this_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(this_dir)
sys.path.insert(0, root_dir)

from sqlalchemy import text, select
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.config import settings
from app.models.user import User, UserRole


async def reset_all():
    print("🔥 Starting complete database reset...")
    async with AsyncSessionLocal() as db:
        tables = [
            "queue_tasks",
            "metadata_drafts",
            "thumbnail_drafts",
            "videos",
            "analytics_records",
            "performance_insights",
            "notification_histories",
            "system_logs",
            "channel_credentials",
            "gcp_projects",
            "channels",
            "system_settings",
        ]

        await db.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        for tbl in tables:
            try:
                await db.execute(text(f"TRUNCATE TABLE {tbl};"))
                print(f"  ✓ Truncated {tbl}")
            except Exception as e:
                print(f"  ⚠ Could not truncate {tbl}: {e}")
        await db.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        await db.commit()

        # Ensure supervisor user exists
        user_tg_id = settings.SUPERVISOR_TELEGRAM_ID or 123456789
        stmt_user = select(User).where(User.telegram_id == user_tg_id)
        res_user = await db.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user:
            user = User(
                telegram_id=user_tg_id,
                username=str(user_tg_id),
                full_name="Supervisor",
                role=UserRole.SUPERVISOR,
                hashed_password=hash_password("admin123"),
                is_active=True
            )
            db.add(user)
            print(f"✅ Created clean supervisor user: {user_tg_id} (Password: admin123)")
        else:
            user.hashed_password = hash_password("admin123")
            db.add(user)
            print(f"✅ Refreshed supervisor user: {user_tg_id} (Password: admin123)")

        await db.commit()
    print("✨ Database reset complete! Everything is 100% clean and fresh from 0.")


if __name__ == "__main__":
    asyncio.run(reset_all())
