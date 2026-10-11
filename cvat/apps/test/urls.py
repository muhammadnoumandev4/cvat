# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from rest_framework import routers

from .views import TaskAnnotationCountsViewSet

router = routers.SimpleRouter(trailing_slash=False)
router.register("test/tasks", TaskAnnotationCountsViewSet, basename="test-tasks")

urlpatterns = router.urls
