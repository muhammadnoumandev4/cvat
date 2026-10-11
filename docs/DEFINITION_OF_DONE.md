# Definition of Done

Written before any code. Each line is ticked only with evidence beside it.

## Environment

- [ ] Machine, OS, CPU, RAM and CVAT commit SHA recorded.
- [ ] Number of COCO images imported recorded.

## Floor (items 1–4)

- [ ] Endpoint returns per-class counts that match an independent count from the COCO json
      for the same images.
- [ ] Page renders the counts as a bar chart.
- [ ] Empty task (no annotations) shows an empty state, not a blank chart.
- [ ] Failed request (server down or 500) shows an error with a retry button.

## Access (item 5)

- [ ] Request with no login → 401. Output saved.
- [ ] Logged-in user with no access to the task → 403. Output saved.
- [ ] Task owner → 200.

## Objective (item 6)

- [ ] MO-1 measured 5 times, median and spread reported, raw output saved.
- [ ] Target met, or missed with the reason written down.

## Beyond the floor

- [ ] Grouping by shape type returns counts that sum to the plain total.
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
