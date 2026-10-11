# Plan — Annotation Analytics

Branch `dev-test01`, forked from `cvat-ai/cvat` `develop` at
`454d60c31a59cb411d82660a3644e29d8fef7bb0`. Budget: 8 hours of work. Image pulls and the
COCO import run in the background and are not counted.

## What I learned before writing this

- A drawn box is a `LabeledShape` (`cvat/apps/engine/models.py`). Its class is
  `LabeledShape.label` → `Label.name`. A shape belongs to a `Job`, a job to a `Segment`, a
  segment to a `Task`. So "per class for a task" is
  `LabeledShape.filter(job__segment__task_id=…).values("label__name")` with `Count`.
- Tracks (`LabeledTrack`) and tags (`LabeledImage`) are separate tables. COCO import only
  creates shapes, but tracks and tags are still annotations, so I count them too.
- Skeleton and child shapes have `parent` set. I count only top-level objects.
- Ground-truth and consensus jobs can hold copies of annotations. Jobs are chosen the way
  CVAT's own `TaskAnnotation` does (see Changes below).
- Access: DRF already refuses anonymous requests (`IsAuthenticated` is the default
  permission class in `cvat/settings/base.py`). Task access goes through OPA via
  `TaskPermission`, the same rules CVAT uses for its own task endpoints (see Changes below
  for which scope).
- The server already runs under uvicorn/ASGI (`cvat/asgi.py`), so a WebSocket route can be
  added there without new dependencies.
- The UI already ships `chart.js` + `react-chartjs-2` and antd.

## Order and time budget

| # | Step | Est. |
|---|------|------|
| 0 | Stack up, COCO subset imported, superuser (background) | — |
| 1 | `cvat/apps/test`: `GET /api/test/tasks/<id>/annotation-counts`, one aggregate query per table | 1h |
| 2–4 | UI route `/tasks/:tid/annotation-stats`: bar chart, empty state, error state with retry; link from task page | 1.5h |
| 5 | Auth: show 401 with no login and 403 for a user with no access (curl, saved output) | 0.5h |
| 6 | Objective MO-1: endpoint latency on the full COCO val task, 5 runs, raw output | 1h |
| 7 | Grouping by shape type (`?group_by=type`) | 0.5h |
| 8–9 | WebSocket live updates, client reconnect with backoff | 2h |
| 10 | Decision record, finish docs, PR to my fork | 1h |

Floor is 1–4. I do not start 8 until 4 works.

## Decided to skip

- Project-level and organization-level counts. Task only, as asked.
- Counting per attribute value. Out of scope.
- New indexes or migrations unless the objective is missed and the query plan shows why.
- Frontend unit tests. I verify the UI by hand and with saved screenshots instead.

## Why grouping by shape type (item 7)

COCO has both bounding boxes and polygons for the same classes. The type split shows
straight away whether a class was annotated as boxes or as segmentation masks, and that is
the first thing a dataset reviewer checks. It is one extra `GROUP BY` column, so the cost is
small.

## Changes during the work

- **Ground truth jobs.** I first counted only `JobType.ANNOTATION` jobs. A review pointed out
  that in a task with a GT pool (honeypots) the pool annotations live only in the ground
  truth job, so they were missing. I now use the same rule as CVAT's own task annotations
  (`TaskAnnotation`, `cvat/apps/dataset_manager/task.py:1033`): annotation jobs, plus the
  ground truth job only in `gt_pool` mode. In plain `gt` mode CVAT itself leaves ground
  truth out of the task's annotations, and so do I. Consensus replicas are never counted.
- **Permission scope.** I planned to reuse `TaskPermission.create_scope_view` ("can see the
  task"). Counts reveal what is annotated, so I used the `view:annotations` scope instead,
  the same rule as `GET /api/tasks/<id>/annotations`. I wired it in as the view's
  `iam_permission_class` so CVAT's `PolicyEnforcer` runs it, like the consensus app does.
- **Objects, not rows.** First run on the COCO task returned 3,953 against COCO's 3,541. CVAT's
  COCO importer stores each part of a multi-polygon segmentation as its own polygon with a
  shared `group` id, so I was counting parts. The 3,953 matches the number of polygon parts
  in the json exactly. Rows sharing `(job, frame, group)` are now counted once, which gives
  3,541 with no per-class differences. Cost: objects a user grouped by hand in CVAT's UI
  with the same label on the same frame now count as one.
- **Filter backends.** CVAT's default filter backends assume a list view with
  `search_fields`, and they crashed this detail-only view (500). The view now sets
  `filter_backends = []`.
- **Mixed-type groups.** A review found that CVAT lets users group shapes of different types
  (`getSelectionGroupState` in `cvat-ui/src/utils/multi-selection.ts` has no type check).
  The split view deduplicated groups per type, so a rectangle and a polygon in one group
  counted once in the total but once under each type. Grouped objects are now taken one
  per `(job, frame, group)` with `Min(type)` as their kind. Checked by adding a rectangle
  to an existing grouped polygon: the plain total, the split total and the per-label sums
  all stayed at 3,541. The plain count path, the one measured in MO-1 and MO-2, did not
  change.
- **Error state crash.** Testing the error state with `cvat_server` stopped crashed the whole
  app. Traefik then sends `/api` to the UI container, which answers 200 with `index.html`.
  The page trusted any 2xx and read `labels.length` on a string. The page now checks the
  response shape. Lesson: "the request failed" does not always arrive as an HTTP error.
- **WebSocket bug found in the browser only.** The first socket test used a Python client and
  passed. In the browser every socket closed with 1006: the handshake offers gzip, Django's
  GZip middleware compressed the replayed response, and decoding it failed. The handler now
  drops `Accept-Encoding` from the replayed request.
- **After review.** Two outside audits read an earlier snapshot. Fixed from them: a socket
  message that is not JSON is now skipped instead of throwing. Retry, the browser coming
  back online, and the tab becoming visible now reconnect the socket at once instead of
  waiting out a backoff of up to 30 s. The spinner shows while any request is loading,
  instead of a stale chart under a switch that had already changed.

## How the time went

From commit times on 12 Oct: plan at 00:50; endpoint, page and grouping by 01:07; then about
an hour of testing against the imported data, which found the parts-versus-objects count,
the 500, the ground truth and mixed-group cases, and the UI crash; WebSocket and reconnect
from 02:09 to 02:19. Image pulls and the COCO download ran in the background before and
during this. The order matched the plan. Testing took a larger share than planned, because
every real run found something that reading the code had not.

## Decision record

**Taken: the socket polls one column and replays the HTTP endpoint in-process.**
`cvat/apps/test/live.py` wraps the ASGI app in `cvat/asgi.py`. Each open socket checks
`Task.updated_date` once a second. CVAT already bumps it on every annotation save
(`_set_updated_date`, `cvat/apps/dataset_manager/task.py:527`). When it changes, the
handler runs the normal HTTP request through Django with the socket's own cookies and
sends the JSON. Login, OPA rules, ground truth handling and counting are therefore the
same code for both, and a refusal maps straight onto a close code.

**Rejected: Django Channels with Redis pub/sub, pushed from annotation-save signals.**
That is the textbook design and would push in milliseconds with no polling.

**What rejecting it cost:**
- Up to 1 s of delay before a change shows (0.2–0.4 s measured).
- One indexed `SELECT` per open socket per second, even when nothing changes. Fine for a
  handful of viewers; it would not scale to thousands of open pages.
- Any change to the task, not only annotations, triggers a recount.

**What it bought:** no new dependency, no image rebuild, and no hooks in CVAT's annotation
save path. That path uses `bulk_create`, which sends no `post_save` signals, so Channels
would have meant changing code in `dataset_manager`. Channels would also have needed a
second, separate auth path for sockets.

**What I would reverse first:** the HTTP request on page load next to the socket. The
socket's first message already carries the counts, so the page fetches them twice on
load. I kept the HTTP call because it gives readable error messages and the Retry path
for item 4. The cost of removing it would be rebuilding that error handling on top of
close codes.

