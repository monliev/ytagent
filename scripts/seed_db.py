import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.channel import Channel
from app.core.security import hash_password
from app.core.config import settings

async def seed():
    print("🌱 Seeding database...")
    async with AsyncSessionLocal() as db:
        # Check if user already exists
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
            print(f"✅ Created supervisor user (Username/Telegram ID: {user_tg_id}, Password: admin123)")
        else:
            # Update password just in case
            user.hashed_password = hash_password("admin123")
            db.add(user)
            print(f"ℹ️ Supervisor user already exists, updated password to: admin123")

        # Check if channel already exists
        stmt_chan = select(Channel).where(Channel.name == "Lofi_Relaxing")
        res_chan = await db.execute(stmt_chan)
        channel = res_chan.scalar_one_or_none()

        if not channel:
            channel = Channel(
                name="Lofi_Relaxing",
                genre="lofi",
                folder_path="./test_nas/Lofi_Relaxing",
                is_active=True,
                thumbnail_style_name="lofi_chill",
                thumbnail_style_prompt="warm lofi bedroom aesthetics, soft focus"
            )
            db.add(channel)
            print("✅ Created channel preset 'Lofi_Relaxing'")
        
        await db.commit()
    print("🌱 Seeding complete!")

if __name__ == "__main__":
    asyncio.run(seed())
