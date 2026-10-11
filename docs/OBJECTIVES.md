# Objectives

Targets set before measuring. Results are filled in only from raw output on this machine.

## Machine

| | |
|---|---|
| Machine | Apple MacBook Pro, Apple M1 Pro (10 cores) |
| RAM | 32 GB (Docker Desktop VM: 8 GB, 10 CPUs) |
| OS | macOS 27.0.1 |
| CVAT commit | `454d60c31a59cb411d82660a3644e29d8fef7bb0` (`develop`, 9 Oct 2026) |
| Images | `cvat/server:dev`, `cvat/ui:dev` with this branch's `cvat/` package and UI bundle mounted |
| Data | COCO 2017 val, first 500 images by file name, 3,541 annotations, 80 labels |

## MO-1 — endpoint latency

| Field | Entry |
|---|---|
| What is measured | Time for `GET /api/test/tasks/<id>/annotation-counts` to return a complete response. |
| How | `curl -w '%{time_total}'` from the host against `http://localhost:8080`, token auth, 1 warm-up request discarded, then 5 timed runs. |
| Target | Median of 5 runs at or below **100 ms**, spread (max − min) at or below 50 ms. |
| Conditions | Local Docker stack as above, the 500-image task, no other requests in flight, nothing else running in Docker. |
| Not included | First request after a server restart, the browser render, the `group_by=type` variant. |

**Why 100 ms.** The chart is the only content on the page, so this request is the page.
Around 100 ms is where a response still feels immediate. The database work is three
`GROUP BY` queries over a few thousand rows, which should take a few milliseconds. Most of
the budget goes to fixed costs I don't control: Traefik, uvicorn, Django middleware, and
the OPA policy call. If the median is far above 100 ms, those fixed costs are the problem,
not the query.

**Result:** _not measured yet._

## MO-2 — the same endpoint at 100× the annotations

| Field | Entry |
|---|---|
| What is measured | Same request as MO-1 on a task with about 354,000 shapes (the 500-image task's shapes copied 100 times in the database). |
| How | Same as MO-1. |
| Target | Median of 5 runs at or below **300 ms**. |
| Conditions | Same as MO-1. |
| Not included | Time to create the copied data. |

**Why.** MO-1 is easy to clear because the data is small. MO-2 tests whether the query
scales: whether `GROUP BY label_id` over the job join uses the `job_id` index or scans the
whole shapes table.

**Result:** _not measured yet._
