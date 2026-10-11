# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from collections import Counter, defaultdict

from django.db.models import CharField, Count, F, Min, Q, Value
from django.db.models.functions import Concat

from cvat.apps.engine.models import (
    JobType,
    LabeledImage,
    LabeledShape,
    LabeledTrack,
    Task,
    ValidationMode,
)

# Tracks and tags have no shape type of their own, so they are reported as a separate kind
_ANNOTATION_KINDS = (
    (LabeledShape, F("type")),
    (LabeledTrack, Value("track")),
    (LabeledImage, Value("tag")),
)

# One object can be stored as several rows sharing a group id, e.g. COCO import turns each
# part of a multi-polygon segmentation into its own polygon. Group ids are unique only within
# a job and frame, so (job, frame, group) identifies the object.
_UNGROUPED = Q(group__isnull=True) | Q(group=0)
_UNGROUPED_ROWS = Count("id", filter=_UNGROUPED)
_GROUPED_OBJECTS = Count(
    Concat("job_id", Value(":"), "frame", Value(":"), "group", output_field=CharField()),
    distinct=True,
    filter=Q(group__gt=0),
)


def count_annotations_per_label(task: Task, *, group_by_type: bool = False) -> list[dict]:
    """
    Count top-level annotation objects (shapes, tracks and tags) per label for a task.

    Rows that share a group id on the same frame of a job are parts of one object and are
    counted once. The cost of this rule: objects a user grouped by hand in CVAT's UI are
    also counted once when they have the same label and frame.

    Jobs are chosen the same way as CVAT's own task annotations (TaskAnnotation in
    cvat/apps/dataset_manager/task.py): annotation jobs, plus the ground truth job only
    when the task uses a GT pool (honeypots). Consensus replicas are never counted.
    Child elements of skeletons have a parent and are not counted separately.
    """

    job_types = [JobType.ANNOTATION]
    if task.data and task.data.validation_mode == ValidationMode.GT_POOL:
        job_types.append(JobType.GROUND_TRUTH)

    counts = Counter()
    counts_by_type = defaultdict(Counter)
    for model, kind in _ANNOTATION_KINDS:
        queryset = model.objects.filter(
            job__segment__task_id=task.id, job__type__in=job_types
        )
        if model is not LabeledImage:
            queryset = queryset.filter(parent__isnull=True)

        if not group_by_type:
            rows = queryset.values("label_id").annotate(
                ungrouped=_UNGROUPED_ROWS, grouped=_GROUPED_OBJECTS
            )
            for row in rows.order_by():
                counts[row["label_id"]] += row["ungrouped"] + row["grouped"]
            continue

        ungrouped = (
            queryset.filter(_UNGROUPED)
            .annotate(kind=kind)
            .values("label_id", "kind")
            .annotate(count=Count("id"))
        )
        for row in ungrouped.order_by():
            counts[row["label_id"]] += row["count"]
            counts_by_type[row["label_id"]][row["kind"]] += row["count"]

        # CVAT lets users group shapes of different types, so a grouped object is counted
        # once, under the alphabetically first type among its parts. This keeps the
        # per-type split summing to the plain count.
        grouped = (
            queryset.filter(group__gt=0)
            .values("label_id", "job_id", "frame", "group")
            .annotate(kind=Min(kind))
            .values_list("label_id", "kind")
            .order_by()
        )
        for label_id, object_kind in grouped.iterator():
            counts[label_id] += 1
            counts_by_type[label_id][object_kind] += 1

    labels = []
    for label in task.get_labels().order_by("id"):
        entry = {"id": label.id, "name": label.name, "color": label.color, "count": counts[label.id]}
        if group_by_type:
            entry["by_type"] = dict(counts_by_type[label.id])
        labels.append(entry)

    return labels
