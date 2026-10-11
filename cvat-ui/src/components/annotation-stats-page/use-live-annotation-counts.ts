// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import {
    useCallback, useEffect, useRef, useState,
} from 'react';

export type LiveState = 'connecting' | 'live' | 'reconnecting' | 'refused';

export interface LiveStatus {
    state: LiveState;
    retryInSeconds: number | null;
}

export interface LiveConnection {
    status: LiveStatus;
    // Skips the remaining backoff wait, e.g. when the user retries or the browser is back online
    reconnectNow: () => void;
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
): LiveConnection {
    const [status, setStatus] = useState<LiveStatus>({ state: 'connecting', retryInSeconds: null });
    const onCountsRef = useRef(onCounts);
    onCountsRef.current = onCounts;
    const reconnectNowRef = useRef<() => void>(() => {});

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
                let data: unknown;
                try {
                    data = JSON.parse(event.data);
                } catch {
                    return; // not counts; the next push replaces it
                }

                failedAttempts = 0;
                setStatus({ state: 'live', retryInSeconds: null });
                onCountsRef.current(data);
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
                retryTimer = window.setTimeout(() => {
                    retryTimer = null;
                    connect();
                }, delay);
            };
        }

        // Only acts while waiting out a backoff; an open or opening socket is left alone
        function reconnectNow(): void {
            if (retryTimer === null) {
                return;
            }
            window.clearTimeout(retryTimer);
            retryTimer = null;
            failedAttempts = 0;
            connect();
        }

        function reconnectWhenVisible(): void {
            if (document.visibilityState === 'visible') {
                reconnectNow();
            }
        }

        reconnectNowRef.current = reconnectNow;
        window.addEventListener('online', reconnectNow);
        document.addEventListener('visibilitychange', reconnectWhenVisible);
        connect();

        return () => {
            stopped = true;
            window.removeEventListener('online', reconnectNow);
            document.removeEventListener('visibilitychange', reconnectWhenVisible);
            if (retryTimer !== null) {
                window.clearTimeout(retryTimer);
            }
            socket?.close();
        };
    }, [taskId, groupByType]);

    const reconnectNow = useCallback(() => reconnectNowRef.current(), []);
    return { status, reconnectNow };
}
