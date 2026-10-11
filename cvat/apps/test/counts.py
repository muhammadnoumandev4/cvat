# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from collections import Counter

from django.db.models import Count

from cvat.apps.engine.models import JobType, LabeledImage, LabeledShape, LabeledTrack, Task


def count_annotations_per_label(task: Task) -> list[dict]:
    """
    Count top-level annotations (shapes, tracks and tags) per label for a task.

    Only regular annotation jobs are counted: ground truth and consensus replica jobs
    hold copies of objects that already exist in the annotation jobs.
    Child elements of skeletons have a parent and are not counted separately.
    """

    counts = Counter()
    for model in (LabeledShape, LabeledTrack, LabeledImage):
        queryset = model.objects.filter(
            job__segment__task_id=task.id, job__type=JobType.ANNOTATION
        )
        if model is not LabeledImage:
            queryset = queryset.filter(parent__isnull=True)

        for row in queryset.values("label_id").annotate(count=Count("id")).order_by():
            counts[row["label_id"]] += row["count"]

    return [
        {"id": label.id, "name": label.name, "color": label.color, "count": counts[label.id]}
        for label in task.get_labels().order_by("id")
    ]
