# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from cvat.apps.engine.models import Task
from cvat.apps.engine.permissions import TaskPermission
from cvat.apps.engine.types import ExtendedRequest
from cvat.apps.iam.permissions import OpenPolicyAgentPermission


class AnnotationCountsPermission:
    """
    Annotation counts reveal what is annotated in a task, so they are guarded by the same
    rule as reading the task's annotations. This app defines no OPA rules of its own.
    """

    @classmethod
    def create(
        cls, request: ExtendedRequest, view, obj: Task | None, iam_context: dict
    ) -> list[OpenPolicyAgentPermission]:
        return [
            TaskPermission.create_base_perm(
                request, view, TaskPermission.Scopes.VIEW_ANNOTATIONS, iam_context, obj
            )
        ]
