"""HTTP opens that ignore environment proxies.

The model servers (op.gitop.vip, upload.shind0.synology.me) are reachable
directly, but desktop sessions commonly export http_proxy/https_proxy/all_proxy
(Clash/mihomo and friends). Those proxies answer 502 for the model hosts, which
silently broke model listing and downloads. urllib reads those variables by
default, so the model fetches go through this opener instead.
"""
from __future__ import annotations

from urllib.request import ProxyHandler, Request, build_opener

_OPENER = build_opener(ProxyHandler({}))


def open_direct(url_or_request, timeout: float):
  """Open *url_or_request* with no proxy, honouring the given timeout."""
  request = url_or_request if isinstance(url_or_request, Request) else Request(url_or_request)
  return _OPENER.open(request, timeout=timeout)
