
import os


def get_int_list(env_name, default=None):
    value = os.getenv(env_name, "")
    if not value:
        return default or []

    return [
        int(item.strip())
        for item in value.split(",")
        if item.strip().isdigit()
    ]


BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR TOKEN")

ADMINS = get_int_list("ADMINS", [000000000])
MODERATORS = get_int_list("MODERATORS", [000000000])

TECH_SUPPORT_USER_ID = int(
    os.getenv("TECH_SUPPORT_USER_ID", "0")
)


def normalize_database_url(url):
    if not url:
        return "sqlite+aiosqlite:///users.db"

    if url.startswith("postgres://"):
        return url.replace(
            "postgres://",
            "postgresql+asyncpg://",
            1
        )

    if url.startswith("postgresql://"):
        return url.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1
        )

    if url.startswith("sqlite:///"):
        return url.replace(
            "sqlite:///",
            "sqlite+aiosqlite:///",
            1
        )

    return url


DB_URL = normalize_database_url(
    os.getenv("DATABASE_URL") or os.getenv("DB_URL")
)

DATABASE_URL = DB_URL
