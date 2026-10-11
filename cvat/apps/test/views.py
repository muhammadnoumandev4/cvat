# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from cvat.apps.engine.models import Task

from .counts import count_annotations_per_label
from .permissions import AnnotationCountsPermission
from .serializers import AnnotationCountsSerializer


@extend_schema(tags=["test"])
class TaskAnnotationCountsViewSet(viewsets.GenericViewSet):
    queryset = Task.objects.select_related("project", "organization", "data__validation_layout")
    iam_permission_class = AnnotationCountsPermission
    iam_supports_organization_params = False
    # Detail-only endpoint: there is no list to search, sort or filter
    filter_backends = []

    @extend_schema(
        summary="Get the number of annotations per label in a task",
        parameters=[
            OpenApiParameter(
                "group_by",
                type=OpenApiTypes.STR,
                enum=["type"],
                description="Also split each label's count by shape type (tracks and tags are separate kinds)",
            ),
        ],
        responses={200: AnnotationCountsSerializer},
    )
    @action(detail=True, methods=["GET"], url_path="annotation-counts")
    def annotation_counts(self, request, pk):
        group_by = request.query_params.get("group_by")
        if group_by not in (None, "type"):
            raise ValidationError({"group_by": "The only supported value is 'type'"})

        task = self.get_object()
        labels = count_annotations_per_label(task, group_by_type=group_by == "type")
        return Response(
            AnnotationCountsSerializer(
                {
                    "task_id": task.id,
                    "total": sum(label["count"] for label in labels),
                    "group_by": group_by,
                    "labels": labels,
                }
            ).data
        )
