# Plan — Annotation Analytics

Branch `dev-test01` from `cvat-ai/cvat` `develop` at `454d60c31a59cb411d82660a3644e29d8fef7bb0`.
Budget 8 hours; image pulls and the COCO import run in the background and are not counted.

## Starting point

- A drawn box is a `LabeledShape`; its class is `LabeledShape.label` → `Label.name`, and it
  reaches its task through `job → segment → task` (`job__segment__task_id`). Tracks, tags and
  intervals are separate tables. Skeleton points are child rows (`parent` set).
- DRF already refuses anonymous requests; task access is decided by OPA through
  `TaskPermission`. The server runs under uvicorn (ASGI), and the UI already ships Chart.js.

## Order and time budget

| # | Step | Est. |
|---|------|------|
| 1 | `cvat/apps/test`: `GET /api/test/tasks/<id>/annotation-counts`, one aggregate per table | 1h |
| 2–4 | Page `/tasks/:tid/annotation-stats`: bar chart, empty state, error with retry | 1.5h |
| 5 | Show 401 without login, 403 without access | 0.5h |
| 6 | MO-1 latency, 5 runs, raw output | 1h |
| 7 | `?group_by=type` | 0.5h |
| 8–9 | WebSocket updates, reconnect with backoff | 2h |
| 10 | Decision record, docs, PR to my fork | 1h |

1–4 is the floor; 8 does not start before 4 works. **Skipped on purpose:** project and
organization counts, per-attribute counts, new indexes unless a target is missed, UI unit
tests (checked by hand with screenshots).

**Why group by type (7):** COCO labels the same classes as boxes, polygons and crowd masks.
The split shows how each class was annotated, which a dataset review asks first, for one
extra `GROUP BY` column.

## Changes during the work

- **Objects, not rows.** The first COCO run gave 3,953, not 3,541: the importer stores each
  part of a multi-polygon as its own row with a shared `group`. Rows sharing
  `(job, position, group)` now count once. Cost: same-label objects grouped by hand also merge.
- **Which jobs.** Copied CVAT's `TaskAnnotation` rule: annotation jobs, plus ground truth
  only in `gt_pool` tasks. Counting annotation jobs alone missed honeypot pools.
- **Scope.** Planned "can view task"; used `view:annotations`, as counts reveal annotations.
- **Found by testing:** a 500 from CVAT's default filter backends; mixed-type groups breaking
  the type split; the page crashing when a down server answered 200 with HTML; browser
  sockets failing on gzip; intervals not counted; an origin check that ignored the scheme;
  late responses overwriting newer charts. Each has its own commit saying what and why.
- **Time.** The order held. Testing took a bigger share than planned, because each run
  against real data found something that reading the code had not.

## Decision record

**Taken:** each socket polls `Task.updated_date` once a second (CVAT bumps it on every
annotation save, `dataset_manager/task.py:527`) and, when it changes, replays the HTTP
endpoint in-process with the socket's cookies (`cvat/apps/test/live.py`). Auth, OPA and
counting are therefore the same code for HTTP and the socket.

**Rejected:** Django Channels with Redis pub/sub, pushed from annotation-save signals. It
pushes in milliseconds without polling.

**What rejecting it cost:** up to 1 s of delay (0.2–0.4 s measured); one indexed `SELECT`
per open socket per second even when idle, which suits a few viewers but not thousands;
and a recount on any task change. In return there is no new dependency, no image rebuild,
and no hook in CVAT's save path. That path uses `bulk_create`, which sends no `post_save`,
so Channels would have meant editing `dataset_manager` and adding a second auth path.

**What I would reverse first:** the HTTP fetch on page load next to the socket, whose first
message already carries the counts. It stays because it gives the clear error and Retry
path for item 4; removing it means rebuilding that error handling on top of close codes.
