# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from collections import Counter, defaultdict
from typing import NamedTuple

from django.db.models import CharField, Count, F, Min, Q, QuerySet, Value
from django.db.models.expressions import Combinable
from django.db.models.functions import Concat

from cvat.apps.engine.models import (
    Annotation,
    JobType,
    LabeledImage,
    LabeledInterval,
    LabeledShape,
    LabeledTrack,
    Task,
    ValidationMode,
)


class _AnnotationTable(NamedTuple):
    model: type[Annotation]
    kind: Combinable
    "What the split by type reports. Only shapes have a type of their own."
    position: str
    "Where the object sits in the media. Group ids are unique per job and position."
    has_children: bool
    "Skeletons store their points as child rows that must not count on their own."


_ANNOTATION_TABLES = (
    _AnnotationTable(LabeledShape, F("type"), "frame", has_children=True),
    _AnnotationTable(LabeledTrack, Value("track"), "frame", has_children=True),
    _AnnotationTable(LabeledImage, Value("tag"), "frame", has_children=False),
    _AnnotationTable(LabeledInterval, Value("interval"), "start", has_children=False),
)

# One object can be stored as several rows sharing a group id, e.g. COCO import turns each
# part of a multi-polygon segmentation into its own polygon
_UNGROUPED = Q(group__isnull=True) | Q(group=0)
_GROUPED = Q(group__gt=0)


def count_annotations_per_label(task: Task, *, group_by_type: bool = False) -> list[dict]:
    """
    Count annotation objects (shapes, tracks, tags and intervals) per label for a task.

    Rows that share a group id at the same position in a job are parts of one object and
    are counted once. The cost of this rule: objects a user grouped by hand in CVAT's UI are
    also counted once when they have the same label and position.

    Jobs are chosen the same way as CVAT's own task annotations (TaskAnnotation in
    cvat/apps/dataset_manager/task.py): annotation jobs, plus the ground truth job only
    when the task uses a GT pool (honeypots). Consensus replicas are never counted.
    """

    job_types = [JobType.ANNOTATION]
    if task.data and task.data.validation_mode == ValidationMode.GT_POOL:
        job_types.append(JobType.GROUND_TRUTH)

    counts = Counter()
    counts_by_type = defaultdict(Counter)
    for table in _ANNOTATION_TABLES:
        queryset = table.model.objects.filter(
            job__segment__task_id=task.id, job__type__in=job_types
        )
        if table.has_children:
            queryset = queryset.filter(parent__isnull=True)

        if group_by_type:
            _count_by_type(queryset, table, counts, counts_by_type)
        else:
            _count(queryset, table, counts)

    labels = []
    for label in task.get_labels().order_by("id"):
        entry = {
            "id": label.id,
            "name": label.name,
            "color": label.color,
            "count": counts[label.id],
        }
        if group_by_type:
            entry["by_type"] = dict(counts_by_type[label.id])
        labels.append(entry)

    return labels


def _count(queryset: QuerySet, table: _AnnotationTable, counts: Counter) -> None:
    object_key = Concat(
        "job_id", Value(":"), table.position, Value(":"), "group", output_field=CharField()
    )
    rows = queryset.values("label_id").annotate(
        ungrouped=Count("id", filter=_UNGROUPED),
        grouped=Count(object_key, distinct=True, filter=_GROUPED),
    )
    for row in rows.order_by():
        counts[row["label_id"]] += row["ungrouped"] + row["grouped"]


def _count_by_type(
    queryset: QuerySet, table: _AnnotationTable, counts: Counter, counts_by_type: defaultdict
) -> None:
    ungrouped = (
        queryset.filter(_UNGROUPED)
        .annotate(kind=table.kind)
        .values("label_id", "kind")
        .annotate(count=Count("id"))
    )
    for row in ungrouped.order_by():
        counts[row["label_id"]] += row["count"]
        counts_by_type[row["label_id"]][row["kind"]] += row["count"]

    # CVAT lets users group shapes of different types, so a grouped object is counted once,
    # under the alphabetically first type among its parts. This keeps the per-type split
    # summing to the plain count.
    grouped = (
        queryset.filter(_GROUPED)
        .values("label_id", "job_id", table.position, "group")
        .annotate(kind=Min(table.kind))
        .values_list("label_id", "kind")
        .order_by()
    )
    for label_id, kind in grouped.iterator():
        counts[label_id] += 1
        counts_by_type[label_id][kind] += 1
