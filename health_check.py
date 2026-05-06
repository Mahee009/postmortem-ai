"""
scripts/health_check.py — verify all services are working before you build
Run this first to catch config errors early.
"""

import os
import sys
import asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.table import Table

console = Console()


async def check_anthropic():
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say OK"}]
        )
        return True, "Connected"
    except Exception as e:
        return False, str(e)[:60]


def check_qdrant():
    try:
        from qdrant_client import QdrantClient
        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        api_key = os.getenv("QDRANT_API_KEY")
        client = QdrantClient(url=url, api_key=api_key) if api_key else QdrantClient(url=url)
        collections = client.get_collections()
        return True, f"Connected ({len(collections.collections)} collections)"
    except Exception as e:
        return False, str(e)[:60]


def check_firecrawl():
    try:
        key = os.getenv("FIRECRAWL_API_KEY", "")
        if not key:
            return False, "FIRECRAWL_API_KEY not set"
        from firecrawl import FirecrawlApp
        app = FirecrawlApp(api_key=key)
        return True, "API key present"
    except Exception as e:
        return False, str(e)[:60]


def check_env():
    required = ["ANTHROPIC_API_KEY", "FIRECRAWL_API_KEY"]
    optional = ["QDRANT_URL", "QDRANT_API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        return False, f"Missing: {', '.join(missing)}"
    return True, "All required env vars set"


async def main():
    console.print("\n[bold]PostMortemAI Health Check[/bold]\n")

    table = Table(show_header=True)
    table.add_column("Service", style="bold")
    table.add_column("Status")
    table.add_column("Detail")

    checks = [
        ("Environment", check_env()),
        ("Qdrant", check_qdrant()),
        ("Firecrawl", check_firecrawl()),
        ("Anthropic API", await check_anthropic()),
    ]

    all_ok = True
    for name, (ok, detail) in checks:
        status = "[green]✓ OK[/green]" if ok else "[red]✗ FAIL[/red]"
        table.add_row(name, status, detail)
        if not ok:
            all_ok = False

    console.print(table)

    if all_ok:
        console.print("\n[green bold]All systems ready. Run: python scripts/ingest_all.py[/green bold]\n")
    else:
        console.print("\n[red bold]Fix the failing services before proceeding.[/red bold]\n")
        console.print("Setup guide:")
        console.print("  Qdrant:     docker run -p 6333:6333 qdrant/qdrant")
        console.print("  Firecrawl:  https://firecrawl.dev (free tier = 500 credits)")
        console.print("  Anthropic:  https://console.anthropic.com\n")


if __name__ == "__main__":
    asyncio.run(main())
