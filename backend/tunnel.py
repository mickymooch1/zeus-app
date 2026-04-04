import asyncio
import re

_tunnel_url: str | None = None


def get_tunnel_url() -> str | None:
    return _tunnel_url


async def start_tunnel_background(port: int) -> None:
    """Start cloudflared quick tunnel. Sets _tunnel_url when URL is found."""
    global _tunnel_url
    try:
        proc = await asyncio.create_subprocess_exec(
            "cloudflared", "tunnel", "--url", f"http://localhost:{port}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async for raw_line in proc.stdout:
            line = raw_line.decode(errors="replace")
            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if match:
                _tunnel_url = match.group(0)
                break
        # Keep reading to prevent buffer fill
        async for _ in proc.stdout:
            pass
    except FileNotFoundError:
        pass  # cloudflared not installed — tunnel won't start, that's fine
    except Exception:
        pass
