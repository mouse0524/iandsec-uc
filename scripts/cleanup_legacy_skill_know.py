import argparse
import asyncio
import sys
from pathlib import Path

from tortoise import Tortoise, connections

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.settings.config import settings


LEGACY_TABLES = [
    "sk_document_line",
    "sk_document_section",
    "sk_document_chunk",
    "sk_message",
    "sk_conversation",
    "sk_upload_task",
    "sk_system_config",
    "sk_document",
    "sk_folder",
]

LEGACY_COMPONENTS = [
    "/skill-know/chat",
    "/skill-know/documents",
    "/skill-know/llm-settings",
    "/skill-know/conversations",
    "/skill-know/evolution",
    "/skill-know/search",
    "/skill-know/skills",
    "/skill-know/graph",
    "/skill-know/quick-setup",
    "/skill-know/upload-tasks",
    "/skill-know/packs",
    "/skill-know/prompts",
]


async def main(apply: bool) -> None:
    sql = [
        "SET FOREIGN_KEY_CHECKS=0;",
        "DELETE FROM `menu` WHERE `path` = '/skill-know' OR `component` IN ({}) OR `path` IN ('chat','documents','llm-settings','conversations','evolution','search','skills','graph','quick-setup','upload-tasks','packs','prompts');".format(
            ",".join(f"'{item}'" for item in LEGACY_COMPONENTS)
        ),
        "DELETE FROM `api` WHERE `path` LIKE '/api/v1/skill_know%';",
        *[f"DROP TABLE IF EXISTS `{table}`;" for table in LEGACY_TABLES],
        "SET FOREIGN_KEY_CHECKS=1;",
    ]
    if not apply:
        print("\n".join(sql))
        return

    await Tortoise.init(config=settings.TORTOISE_ORM)
    conn = connections.get("mysql")
    try:
        # ponytail: MySQL-only cleanup for this app's configured backend; add dialect branching if another DB is enabled.
        for statement in sql:
            await conn.execute_script(statement)
        print("legacy Skill-Know data cleaned")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="execute cleanup; omit to print SQL only")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
