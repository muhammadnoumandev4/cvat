# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from cvat.apps.engine.models import Task

from .counts import count_annotations_per_label
from .permissions import AnnotationCountsPermission
from .serializers import AnnotationCountsSerializer


@extend_schema(tags=["test"])
class TaskAnnotationCountsViewSet(viewsets.GenericViewSet):
    queryset = Task.objects.select_related("project", "organization")
    iam_permission_class = AnnotationCountsPermission
    iam_supports_organization_params = False

    @extend_schema(
        summary="Get the number of annotations per label in a task",
        responses={200: AnnotationCountsSerializer},
    )
    @action(detail=True, methods=["GET"], url_path="annotation-counts")
    def annotation_counts(self, request, pk):
        task = self.get_object()
        labels = count_annotations_per_label(task)
        return Response(
            AnnotationCountsSerializer(
                {"task_id": task.id, "total": sum(label["count"] for label in labels), "labels": labels}
            ).data
        )
