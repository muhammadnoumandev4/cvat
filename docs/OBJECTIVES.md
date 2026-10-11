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

**Result: met.** Median **29.3 ms**, min 28.8 ms, max 32.9 ms, spread 4.1 ms.

My first run broke the stated method: I used HTTP Basic auth instead of a token, and got a
median of about 560 ms. A trivial endpoint (`/api/users/self`) took the same 540–550 ms with
Basic auth and 18 ms with a token. Basic auth makes Django re-hash the password on every
request, which is deliberately slow. That cost belongs to the auth method, not the endpoint.
The browser uses a session, so token auth is the realistic case. I re-ran as written and
kept both runs below.

```
# MO-1 2026-10-11T20:45:40Z task 2 (500 images, 3541 objects)
run 1: http=200 time_total=0.555105s
run 2: http=200 time_total=0.554005s
run 3: http=200 time_total=0.568855s
run 4: http=200 time_total=0.567320s
run 5: http=200 time_total=0.559815s

# MO-1 (method as written: token auth) 2026-10-11T20:46:03Z task 2 (500 images, 3541 objects)
run 1: http=200 time_total=0.032902s
run 2: http=200 time_total=0.029255s
run 3: http=200 time_total=0.028810s
run 4: http=200 time_total=0.029520s
run 5: http=200 time_total=0.028834s
```

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

**Result: met, with almost no margin.** Median **295.2 ms**, min 295.0 ms, max 298.8 ms,
spread 3.8 ms. It reported 354,100 objects, exactly 100 × 3,541.

```
# MO-2 2026-10-11T20:46:27Z task 2 with shapes copied 99 extra times (token auth)
total objects reported: 354100
run 1: http=200 time_total=0.298786s
run 2: http=200 time_total=0.297974s
run 3: http=200 time_total=0.295243s
run 4: http=200 time_total=0.295066s
run 5: http=200 time_total=0.294950s
```

Where the time goes (`EXPLAIN ANALYZE` of the shapes query, same data):

- The plan uses `engine_labeledshape_job_id` (bitmap index scan) for the task's 5 jobs,
  then reads all 395,300 of the task's rows from the heap. It never scans other tasks.
- The plain `GROUP BY label_id` count took 270 ms. Adding the distinct `(job, frame,
  group)` count, which merges multi-part polygons into one object, took 375 ms and spilled
  a 14.8 MB sort to disk (`work_mem` is the default 4 MB).

So cost grows linearly with the task's annotation rows. The next step, which I did not
take, would be a covering index on `(job_id, label_id, frame, "group")` for an index-only
scan, or a counter table updated when annotations are saved. I did not add a migration for
a target that was already met. The synthetic copies were deleted afterwards (the task is
back to 3,541).
