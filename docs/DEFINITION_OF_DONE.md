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
- [ ] Page renders the counts as a bar chart.
- [ ] Empty task (no annotations) shows an empty state, not a blank chart.
- [ ] Failed request (server down or 500) shows an error with a retry button.

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
- [ ] Chart updates live over WebSocket when a box is added or deleted in a job.
- [ ] Page reconnects after the WebSocket drops (server restart) and shows the
      connection state.
- [ ] Decision record at the end of the Plan.

## Hygiene

- [ ] Commits are small and readable. Plan and this file are committed before any code.
- [ ] No dead code, commented-out blocks or stray files.
- [ ] Everything I did not finish is listed below.

## Not finished

_(Filled in at the end.)_
