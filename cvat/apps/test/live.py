# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

"""
Live annotation counts over a WebSocket.

ws://<host>/api/test/tasks/<id>/annotation-counts/ws[?group_by=type]

Every annotation save touches the task's updated_date (see _set_updated_date in
cvat/apps/dataset_manager/task.py), so the socket polls that one column and recounts only
when it changes. Counts are produced by running the regular HTTP endpoint in-process with
the socket's cookies, so login, OPA access rules and counting are the same code as the REST
call. When the HTTP call is refused, the socket closes with 4000 + the HTTP status
(4401, 4403, 4404).
"""

import asyncio
import re
from urllib.parse import urlsplit

from asgiref.sync import sync_to_async

from cvat.apps.engine.models import Task

POLL_INTERVAL = 1.0  # seconds

_SOCKET_PATH = re.compile(r"^/api/test/tasks/(?P<task_id>\d+)/annotation-counts/ws$")


def route_websockets(django_app):
    async def application(scope, receive, send):
        if scope["type"] == "websocket":
            match = _SOCKET_PATH.match(scope["path"])
            if match:
                return await _serve_counts(
                    django_app, scope, receive, send, int(match["task_id"])
                )

            await receive()  # websocket.connect
            return await send({"type": "websocket.close"})

        return await django_app(scope, receive, send)

    return application


def _header(scope, name: bytes) -> str:
    return next((v.decode("latin-1") for k, v in scope["headers"] if k == name), "")


def _is_same_origin(scope) -> bool:
    # Browsers attach session cookies to cross-site WebSocket handshakes, and CSRF
    # protection does not cover them, so the origin is checked here
    return urlsplit(_header(scope, b"origin")).netloc == _header(scope, b"host")


async def _fetch_counts(django_app, scope, task_id: int) -> tuple[int, str]:
    http_scope = {
        **scope,
        "type": "http",
        "method": "GET",
        "scheme": {"wss": "https"}.get(scope.get("scheme"), "http"),
        "path": f"/api/test/tasks/{task_id}/annotation-counts",
        "raw_path": f"/api/test/tasks/{task_id}/annotation-counts".encode(),
        # Browsers offer gzip in the handshake; the body is sent as a text frame, not HTTP
        "headers": [(k, v) for k, v in scope["headers"] if k != b"accept-encoding"],
    }
    status = 500
    body = []
    request_sent = False

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}

        # Django keeps listening for a client disconnect until the response is sent,
        # then cancels this wait. The in-process caller never disconnects.
        await asyncio.Future()

    async def send(message):
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]
        elif message["type"] == "http.response.body":
            body.append(message.get("body", b""))

    await django_app(http_scope, receive, send)
    return status, b"".join(body).decode()


@sync_to_async
def _get_task_version(task_id: int):
    return Task.objects.filter(id=task_id).values_list("updated_date", flat=True).first()


async def _serve_counts(django_app, scope, receive, send, task_id: int):
    await receive()  # websocket.connect
    if not _is_same_origin(scope):
        return await send({"type": "websocket.close", "code": 4403})

    await send({"type": "websocket.accept"})

    disconnected = asyncio.Event()

    async def wait_for_disconnect():
        while (await receive())["type"] != "websocket.disconnect":
            pass
        disconnected.set()

    watcher = asyncio.create_task(wait_for_disconnect())
    try:
        version = None
        while not disconnected.is_set():
            new_version = await _get_task_version(task_id)
            if version is None or new_version != version:
                version = new_version
                status, body = await _fetch_counts(django_app, scope, task_id)
                if status != 200:
                    return await send({"type": "websocket.close", "code": 4000 + status})
                await send({"type": "websocket.send", "text": body})

            try:
                await asyncio.wait_for(disconnected.wait(), POLL_INTERVAL)
            except asyncio.TimeoutError:
                pass
    finally:
        watcher.cancel()
