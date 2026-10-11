// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import { useEffect, useRef, useState } from 'react';

export type LiveState = 'connecting' | 'live' | 'reconnecting' | 'refused';

export interface LiveStatus {
    state: LiveState;
    retryInSeconds: number | null;
}

const MAX_RETRY_DELAY_MS = 30000;

// The server closes with 4000 + HTTP status when the counts request is refused.
// Reconnecting would be refused again, so the page stops there.
function isRefusal(code: number): boolean {
    return code >= 4400 && code < 4500;
}

export function useLiveAnnotationCounts(
    taskId: number,
    groupByType: boolean,
    onCounts: (data: unknown) => void,
): LiveStatus {
    const [status, setStatus] = useState<LiveStatus>({ state: 'connecting', retryInSeconds: null });
    const onCountsRef = useRef(onCounts);
    onCountsRef.current = onCounts;

    useEffect(() => {
        let socket: WebSocket | null = null;
        let retryTimer: number | null = null;
        let failedAttempts = 0;
        let stopped = false;

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const query = groupByType ? '?group_by=type' : '';
        const url = `${protocol}//${window.location.host}/api/test/tasks/${taskId}/annotation-counts/ws${query}`;

        function connect(): void {
            setStatus((prev) => ({
                state: prev.state === 'reconnecting' ? 'reconnecting' : 'connecting',
                retryInSeconds: null,
            }));
            socket = new WebSocket(url);

            socket.onmessage = (event: MessageEvent<string>) => {
                failedAttempts = 0;
                setStatus({ state: 'live', retryInSeconds: null });
                onCountsRef.current(JSON.parse(event.data));
            };

            socket.onclose = (event: CloseEvent) => {
                if (stopped) {
                    return;
                }

                if (isRefusal(event.code)) {
                    setStatus({ state: 'refused', retryInSeconds: null });
                    return;
                }

                // Exponential backoff so a restarting server is not flooded by every open page.
                // The server sends fresh counts on connect, so nothing missed while offline is lost.
                const delay = Math.min(1000 * 2 ** failedAttempts, MAX_RETRY_DELAY_MS);
                failedAttempts += 1;
                setStatus({ state: 'reconnecting', retryInSeconds: Math.round(delay / 1000) });
                retryTimer = window.setTimeout(connect, delay);
            };
        }

        connect();

        return () => {
            stopped = true;
            if (retryTimer !== null) {
                window.clearTimeout(retryTimer);
            }
            socket?.close();
        };
    }, [taskId, groupByType]);

    return status;
}
