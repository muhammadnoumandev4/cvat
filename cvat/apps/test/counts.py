# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from collections import Counter, defaultdict

from django.db.models import Count, F, Value

from cvat.apps.engine.models import JobType, LabeledImage, LabeledShape, LabeledTrack, Task

# Tracks and tags have no shape type of their own, so they are reported as a separate kind
_ANNOTATION_KINDS = (
    (LabeledShape, F("type")),
    (LabeledTrack, Value("track")),
    (LabeledImage, Value("tag")),
)


def count_annotations_per_label(task: Task, *, group_by_type: bool = False) -> list[dict]:
    """
    Count top-level annotations (shapes, tracks and tags) per label for a task.

    Only regular annotation jobs are counted: ground truth and consensus replica jobs
    hold copies of objects that already exist in the annotation jobs.
    Child elements of skeletons have a parent and are not counted separately.
    """

    counts = Counter()
    counts_by_type = defaultdict(Counter)
    for model, kind in _ANNOTATION_KINDS:
        queryset = model.objects.filter(
            job__segment__task_id=task.id, job__type=JobType.ANNOTATION
        )
        if model is not LabeledImage:
            queryset = queryset.filter(parent__isnull=True)

        if group_by_type:
            rows = queryset.annotate(kind=kind).values("label_id", "kind")
        else:
            rows = queryset.values("label_id")

        for row in rows.annotate(count=Count("id")).order_by():
            counts[row["label_id"]] += row["count"]
            if group_by_type:
                counts_by_type[row["label_id"]][row["kind"]] += row["count"]

    labels = []
    for label in task.get_labels().order_by("id"):
        entry = {"id": label.id, "name": label.name, "color": label.color, "count": counts[label.id]}
        if group_by_type:
            entry["by_type"] = dict(counts_by_type[label.id])
        labels.append(entry)

    return labels
