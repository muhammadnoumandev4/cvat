# Definition of Done

Written before any code. Each line is ticked only with evidence beside it.

## Environment

- [x] Machine, OS, CPU, RAM and CVAT commit SHA recorded. → `docs/OBJECTIVES.md`, Machine table.
- [x] Number of COCO images imported recorded. → 500 images (first 500 of val2017 by file
      name), 3,541 annotations, 80 labels. Task id 2.

## Floor (items 1–4)

- [x] Endpoint returns per-class counts that match an independent count from the COCO json
      for the same images. → API total 3,541, COCO total 3,541, **0 mismatches across 80
      classes**. The first run gave 3,953 (polygon parts, not objects); see Plan → Changes.
      `group_by=type`: 3,504 polygons + 37 masks = 3,541; COCO has 37 crowd (RLE) objects.
- [x] Page renders the counts as a bar chart. → Reached from the task's Actions menu
      ([1](evidence/1-task-actions-menu.jpg)). 80 bars sorted by count in label colours,
      "3541 annotations across 80 labels" ([2](evidence/2-chart.jpg)). The split toggle
      draws stacked mask/polygon bars ([3](evidence/3-split-by-type.jpg)).
- [x] Empty task (no annotations) shows an empty state, not a blank chart. → Task 3, one
      image, two labels, API `total: 0`: "This task has no annotations yet"
      ([4](evidence/4-empty-task.jpg)).
- [x] Failed request (server down or 500) shows an error with a retry button. → Task
      99999 gives a 404 with the server's message and Retry ([5](evidence/5-error-404.jpg)).
      With the page open I stopped `cvat_server` and toggled the switch: error with Retry
      ([6](evidence/6-error-server-down.jpg)). I started the server and clicked Retry: the
      chart came back. The first attempt crashed the whole app
      ([0](evidence/0-crash-before-fix.jpg)); see Plan → Changes.

## Access (item 5)

- [x] Request with no login → 401.
- [x] Logged-in user with no access to the task → 403.
- [x] Task owner → 200.
- [x] Access follows the task: the same user gets 200 once assigned, and 403 again after.

```
$ curl -i http://localhost:8080/api/test/tasks/2/annotation-counts   # no login
HTTP/1.1 401 Unauthorized
{"detail":"Authentication credentials were not provided."}

$ curl -i -u outsider:*** http://localhost:8080/api/test/tasks/2/annotation-counts   # logged in, no access to task 2
HTTP/1.1 403 Forbidden
{"detail":"You do not have permission to perform this action."}

$ curl -i -u admin_test:*** http://localhost:8080/api/test/tasks/2/annotation-counts   # task owner
HTTP/1.1 200 OK
{"task_id":2,"total":3541,"group_by":null,"labels":[{"id":81,"name":"person","color":"#c06060","count":1088},{"id":82,"n
$ curl -i -u admin_test:*** "http://localhost:8080/api/test/tasks/2/annotation-counts?group_by=bad"
HTTP/1.1 400 Bad Request
{"group_by":"The only supported value is 'type'"}

$ curl -i -u admin_test:*** http://localhost:8080/api/test/tasks/99999/annotation-counts
HTTP/1.1 404 Not Found
{"detail":"No Task matches the given query."}

# assign task 2 to outsider (user id 2), repeat, then unassign
PATCH assignee -> 200
$ curl -i -u outsider:*** http://localhost:8080/api/test/tasks/2/annotation-counts   # now the task assignee
HTTP/1.1 200 OK
PATCH assignee null -> 200
$ curl -i -u outsider:*** http://localhost:8080/api/test/tasks/2/annotation-counts   # unassigned again
HTTP/1.1 403 Forbidden
```

## Objective (item 6)

- [x] MO-1 measured 5 times, median and spread reported, raw output saved. → 29.3 ms
      median, 4.1 ms spread (`docs/OBJECTIVES.md`). MO-2 at 100×: 295.2 ms median.
- [x] Target met, or missed with the reason written down. → Both met. MO-2 with almost no
      margin, and the reason is written down. The first MO-1 run broke the stated method
      (Basic auth, about 560 ms); that is kept and explained.

## Beyond the floor

- [x] Grouping by shape type returns counts that sum to the plain total. → Every label's
      `by_type` sums to its `count`; total 3,541 both ways.
- [x] Chart updates live over WebSocket when a box is added or deleted in a job. → With the
      page open, adding 20 zebra boxes to job 5 through the annotations API changed it from
      3,541 to 3,561 within 2 s, with no reload ([7](evidence/7-live-after-adding-20.jpg)).
      In the socket test below, each add or delete arrived about 0.2–0.4 s after the edit.
      The socket refuses exactly like the HTTP endpoint (4401 / 4403 / 4404), and rejects a
      cross-site Origin at the handshake.

```
# live push test 2026-10-11T21:13:49Z: socket open on task 2, job 5 edited through the REST API
02:13:52 delete test box -> 200
02:13:56 add zebra box -> 200
02:14:00 delete test box -> 200
+ 0.16s push: total=3542 zebra=32
+ 3.23s push: total=3541 zebra=31
+ 7.30s push: total=3542 zebra=32
+11.36s push: total=3541 zebra=31

# refusals
no login:
closed: ConnectionClosedError 4401 
outsider (no access):
closed: ConnectionClosedError 4403 
owner, cross-site Origin:
closed: InvalidStatus None None
owner, missing task:
closed: ConnectionClosedError 4404
```
- [x] Page reconnects after the WebSocket drops (server restart) and shows the
      connection state. → I stopped `cvat_server` with the page open. The badge showed
      "Connection lost, reconnecting in 4s", backing off 1, 2, 4, 8, 16 then 30 s, and the
      chart kept the last counts ([8](evidence/8-reconnecting.png)). While the page was
      disconnected I deleted the 20 boxes in the database. After the server came back the
      page reconnected on its own and showed "Live" with 3,541, the change it had missed
      ([9](evidence/9-recovered.jpg)).
- [x] Decision record at the end of the Plan. → `docs/PLAN.md`, Decision record.

## Added after the first submission draft

- [x] Automated tests. → `cvat/apps/test/tests/test_annotation_counts.py`, 16 tests, all
      passing. They run with CVAT's own test settings, the same way CI does:
      `DJANGO_SETTINGS_MODULE=cvat.settings.testing python manage.py test cvat.apps.test`.
      My run used the `cvat/server:dev` image with `cvat/requirements/testing.txt`
      installed, inside the OPA container's network so `localhost:8181` reaches OPA (CI uses
      host networking for that).

```
test_anonymous_is_refused [AnnotationCountsApiTest] ... ok
test_assignee_gets_access [AnnotationCountsApiTest] ... ok
test_group_by_type [AnnotationCountsApiTest] ... ok
test_missing_task [AnnotationCountsApiTest] ... ok
test_owner_gets_counts [AnnotationCountsApiTest] ... ok
test_unknown_group_by_is_rejected [AnnotationCountsApiTest] ... ok
test_user_without_access_is_refused [AnnotationCountsApiTest] ... ok
test_counts_shapes_tracks_and_tags_per_label [CountAnnotationsTest] ... ok
test_ground_truth_counted_only_in_gt_pool_mode [CountAnnotationsTest] ... ok
test_grouped_parts_are_one_object_per_frame [CountAnnotationsTest] ... ok
test_labels_without_annotations_are_listed_with_zero [CountAnnotationsTest] ... ok
test_skeleton_is_one_object [CountAnnotationsTest] ... ok
test_type_split_sums_to_count_for_mixed_type_groups [CountAnnotationsTest] ... ok
test_cross_site_origin_is_rejected_before_accept [LiveAnnotationCountsTest] ... OK
test_pushes_counts_on_connect_and_after_change [LiveAnnotationCountsTest] ... ok
test_refusal_closes_with_http_status [LiveAnnotationCountsTest] ... ok
Ran 16 tests in 1.873s
OK
```

- [x] Tracks, tags and skeletons checked on live data. → Task 4 (10 COCO images), annotated
      through the job annotations API, the same call the editor makes. The database holds 9
      rows; the API counts 5 objects. A track with 3 keyframes is one object, and a skeleton
      with 2 points is one object ([10](evidence/10-tracks-tags-skeleton.jpg)). This check
      also found that the axis showed fractional ticks for small counts; fixed.

```
# task 4 (10 COCO images): 1 car box, 1 car track with 3 keyframes, 2 weather tags, 1 body skeleton with 2 points
PATCH job 7 annotations (create) -> 200
rows in DB: shapes=4 (skeleton + 2 elements + box), tracks=1, tracked shapes=3, tags=2
API total: 5
  car      count=2 by_type={'rectangle': 1, 'track': 1}
  weather  count=2 by_type={'tag': 2}
  body     count=1 by_type={'skeleton': 1}
```

## Hygiene

- [x] Commits are small and readable. Plan and this file are committed before any code.
      → First commit `f21daee` holds only these two documents. Each fix found in testing
      is its own commit, saying what broke and why.
- [x] No dead code, commented-out blocks or stray files. → 674 added lines of feature code and
      244 of tests, 0 removed, outside `docs/`: `cvat/apps/test/`; one line in `cvat/settings/base.py`; one `include` in
      `cvat/urls.py`; two lines in `cvat/asgi.py`; the page folder, one route and one menu
      item in the UI.
- [x] Everything I did not finish is listed below.

## Not finished

- **No UI tests.** The backend and the socket have automated tests (above). The page was
  checked by hand with screenshots; there are no Jest or Cypress tests for it.
- **No covering index.** MO-2 met its target with almost no margin. The next step is
  written in `docs/OBJECTIVES.md` but not done.
- **Recovery can take up to 30 s** after a long outage, because of the backoff cap. There is
  no "reconnect now" button, and the page does not listen for the browser's `online` event.
- **Prebuilt images, not rebuilt.** I ran the `cvat/server:dev` and `cvat/ui:dev` images
  with this branch's `cvat/` package and UI bundle bind-mounted, through a local compose
  override kept outside the repo. I chose not to rebuild them. The UI image runs the same
  `yarn run build:cvat-ui` I ran, and the server image copies the same `cvat/` folder I
  mounted. A rebuild would cost about an hour of downloads and compiling and would test
  CVAT's Dockerfiles rather than this change.
- **Loom recording.** Not part of the repository. It is recorded and linked separately.
