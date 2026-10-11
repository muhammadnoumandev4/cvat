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
