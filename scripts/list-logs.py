import sys
import argparse
import asyncio
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from shared.database import get_database_url
from shared.models import SystemEvent

async def main():
    parser = argparse.ArgumentParser(description="Query UnifyRoute system event logs.")
    parser.add_argument("search", nargs="?", help="Search term for message or details")
    parser.add_argument("--level", choices=["INFO", "WARNING", "ERROR", "CRITICAL"], help="Filter by severity level")
    parser.add_argument("--component", help="Filter by component (e.g., selfheal, api-gateway)")
    parser.add_argument("--limit", type=int, default=50, help="Number of logs to retrieve (default: 50)")

    args = parser.parse_args()

    engine = create_async_engine(get_database_url(), echo=False)
    session_maker = async_sessionmaker(engine)

    async with session_maker() as session:
        stmt = select(SystemEvent)

        filters = []
        if args.level:
            filters.append(SystemEvent.level == args.level.upper())
        if args.component:
            filters.append(SystemEvent.component == args.component)
        if args.search:
            search_param = f"%{args.search}%"
            # Using basic LIKE on message for sqlite compatibility
            filters.append(SystemEvent.message.ilike(search_param))

        if filters:
            stmt = stmt.where(*filters)
        
        stmt = stmt.order_by(SystemEvent.timestamp.desc()).limit(args.limit)
        
        result = await session.execute(stmt)
        events = result.scalars().all()

        if not events:
            print("No events found matching your criteria.")
            return

        # Print cleanly
        print(f"{'TIMESTAMP':<25} {'LEVEL':<10} {'COMPONENT':<15} {'EVENT_TYPE':<25} MESSAGE")
        print("-" * 100)
        for e in events:
            # Color coding setup (basic ANSI)
            color_start = ""
            color_end = ""
            if e.level == "ERROR" or e.level == "CRITICAL":
                color_start = "\033[91m"
                color_end = "\033[0m"
            elif e.level == "WARNING":
                color_start = "\033[93m"
                color_end = "\033[0m"
            elif e.level == "INFO":
                color_start = "\033[94m"
                color_end = "\033[0m"

            # localise time for display
            ts = e.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            print(f"{ts:<25} {color_start}{e.level:<10}{color_end} {e.component:<15} {e.event_type:<25} {e.message}")
            if e.details:
                import json
                try:
                    pretty_details = json.dumps(e.details, indent=2)
                    for line in pretty_details.split('\n'):
                        print(f"  {line}")
                except Exception:
                    print(f"  {e.details}")

if __name__ == "__main__":
    asyncio.run(main())
