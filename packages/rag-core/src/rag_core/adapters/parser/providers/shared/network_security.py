"""Network security and SSRF mitigation utilities for document downloading."""

import asyncio
import ipaddress
import socket
import threading
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

import httpcore
import httpx


class SafeAsyncNetworkBackend(httpcore.AnyIOBackend):
    """Network backend that mitigates SSRF by resolving DNS and validating IP addresses before connecting."""

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        try:
            loop = asyncio.get_running_loop()
            addr_info = await loop.run_in_executor(
                None, socket.getaddrinfo, host, port, socket.AF_UNSPEC, socket.SOCK_STREAM
            )
        except Exception as exc:
            raise httpcore.ConnectError(f"DNS resolution failed for {host}: {exc}") from exc

        safe_ips = []
        for _family, _socktype, _proto, _canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    raise ValueError(f"SSRF Prevention: URL resolves to private/loopback/link-local IP: {ip_str}")
                safe_ips.append(ip_str)
            except ValueError as ve:
                raise httpcore.ConnectError(str(ve)) from ve

        if not safe_ips:
            raise httpcore.ConnectError(f"No safe IP addresses found for host {host}")

        # Connect directly to the resolved IP to prevent DNS rebinding attacks.
        target_ip = safe_ips[0]

        # Use type ignore since connect_tcp is dynamically typed on httpcore.AnyIOBackend
        return await super().connect_tcp(  # type: ignore
            host=target_ip,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


_safe_http_client: httpx.AsyncClient | None = None
_safe_client_lock = threading.Lock()


def get_safe_http_client() -> httpx.AsyncClient:
    """Return a shared httpx.AsyncClient instance pre-configured with the SafeAsyncNetworkBackend."""
    global _safe_http_client
    if _safe_http_client is None:
        with _safe_client_lock:
            if _safe_http_client is None:
                try:
                    from app_http_client.config import get_http_client_settings

                    settings = get_http_client_settings()
                    limits = httpx.Limits(
                        max_connections=settings.max_connections,
                        max_keepalive_connections=settings.max_keepalive_connections,
                        keepalive_expiry=settings.keepalive_expiry,
                    )
                except Exception:
                    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5, keepalive_expiry=5.0)

                transport = httpx.AsyncHTTPTransport(verify=True, limits=limits)
                transport._pool._network_backend = SafeAsyncNetworkBackend()  # type: ignore
                _safe_http_client = httpx.AsyncClient(transport=transport)
    return _safe_http_client


def _validate_ssrf(url: str) -> None:
    """Validate that the URL does not resolve to a private, loopback, or link-local address (SSRF mitigation)."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Invalid URL: missing hostname")

        addr_info = socket.getaddrinfo(hostname, None)
        for _family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValueError(f"SSRF Prevention: URL resolves to private/loopback/link-local IP: {ip_str}")
    except ValueError as ve:
        raise ve
    except Exception as exc:
        raise ValueError(f"SSRF Validation failed during DNS resolution: {exc}") from exc
