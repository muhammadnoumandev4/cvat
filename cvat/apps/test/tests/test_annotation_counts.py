# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

import json

from asgiref.testing import ApplicationCommunicator
from django.core.asgi import get_asgi_application
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from cvat.apps.engine.models import (
    Data,
    Job,
    JobType,
    Label,
    LabeledImage,
    LabeledInterval,
    LabeledShape,
    LabeledTrack,
    LabelType,
    Segment,
    Task,
    TrackedShape,
    ValidationLayout,
    ValidationMode,
)
from cvat.apps.engine.tests.utils import ForceLogin
from cvat.apps.iam.models import User
from cvat.apps.test.counts import count_annotations_per_label
from cvat.apps.test.live import route_websockets


class _TaskFixture:
    def make_task(self, owner: User) -> None:
        self.task = Task.objects.create(
            name="counts",
            owner=owner,
            data=Data.objects.create(size=20, stop_frame=19, image_quality=50),
        )
        self.job = self.make_job(0, 9)
        self.second_job = self.make_job(10, 19)
        self.car = Label.objects.create(task=self.task, name="car")
        self.person = Label.objects.create(task=self.task, name="person")

    def make_job(self, start: int, stop: int, job_type: JobType = JobType.ANNOTATION) -> Job:
        segment = Segment.objects.create(task=self.task, start_frame=start, stop_frame=stop)
        return Job.objects.create(segment=segment, type=job_type)

    def add_shape(self, label: Label, *, job: Job = None, frame=0, group=0, type="rectangle"):
        return LabeledShape.objects.create(
            job=job or self.job, label=label, frame=frame, group=group, type=type, points=[0, 0]
        )


class CountAnnotationsTest(_TaskFixture, TestCase):
    def setUp(self):
        self.make_task(User.objects.create_user(username="owner"))

    def counts(self, **kwargs) -> dict[str, dict]:
        return {label["name"]: label for label in count_annotations_per_label(self.task, **kwargs)}

    def test_counts_shapes_tracks_and_tags_per_label(self):
        self.add_shape(self.car)
        self.add_shape(self.car, job=self.second_job, frame=12)
        track = LabeledTrack.objects.create(job=self.job, label=self.car, frame=0)
        TrackedShape.objects.create(track=track, frame=0, type="rectangle", points=[0, 0])
        TrackedShape.objects.create(track=track, frame=5, type="rectangle", points=[0, 0])
        LabeledImage.objects.create(job=self.job, label=self.person, frame=3)

        counts = self.counts()

        self.assertEqual(counts["car"]["count"], 3)  # a track with 2 keyframes is one object
        self.assertEqual(counts["person"]["count"], 1)

    def test_intervals_are_counted_and_grouped_by_start(self):
        LabeledInterval.objects.create(job=self.job, label=self.car, start=0, stop=4)
        for _ in range(2):  # two parts of one grouped interval
            LabeledInterval.objects.create(job=self.job, label=self.car, start=5, stop=9, group=3)

        car = self.counts(group_by_type=True)["car"]

        self.assertEqual(car["count"], 2)
        self.assertEqual(car["by_type"], {"interval": 2})

    def test_labels_without_annotations_are_listed_with_zero(self):
        self.assertEqual(
            {name: c["count"] for name, c in self.counts().items()}, {"car": 0, "person": 0}
        )

    def test_skeleton_is_one_object(self):
        skeleton = Label.objects.create(task=self.task, name="body", type=LabelType.SKELETON)
        head = Label.objects.create(task=self.task, name="head", parent=skeleton)
        tail = Label.objects.create(task=self.task, name="tail", parent=skeleton)
        root = self.add_shape(skeleton, type="skeleton")
        for element in (head, tail):
            LabeledShape.objects.create(
                job=self.job, label=element, parent=root, frame=0, type="points", points=[0, 0]
            )

        counts = self.counts()

        self.assertEqual(counts["body"]["count"], 1)
        self.assertNotIn("head", counts)

    def test_grouped_parts_are_one_object_per_frame(self):
        for _ in range(3):
            self.add_shape(self.person, group=7, type="polygon")
        self.add_shape(self.person, group=7, frame=1, type="polygon")  # same id, other frame
        self.add_shape(self.person, job=self.second_job, group=7, frame=10, type="polygon")

        self.assertEqual(self.counts()["person"]["count"], 3)

    def test_type_split_sums_to_count_for_mixed_type_groups(self):
        self.add_shape(self.car, group=4, type="rectangle")
        self.add_shape(self.car, group=4, type="polygon")
        self.add_shape(self.car, type="mask")
        LabeledImage.objects.create(job=self.job, label=self.car, frame=0)

        car = self.counts(group_by_type=True)["car"]

        self.assertEqual(car["count"], 3)
        self.assertEqual(car["by_type"], {"polygon": 1, "mask": 1, "tag": 1})

    def test_ground_truth_counted_only_in_gt_pool_mode(self):
        gt_job = self.make_job(0, 19, JobType.GROUND_TRUTH)
        consensus_job = self.make_job(0, 9, JobType.CONSENSUS_REPLICA)
        self.add_shape(self.car)
        self.add_shape(self.car, job=gt_job)
        self.add_shape(self.car, job=consensus_job)

        self.assertEqual(self.counts()["car"]["count"], 1)

        ValidationLayout.objects.create(
            task_data=self.task.data, mode=ValidationMode.GT_POOL, frames=[], disabled_frames=[]
        )
        self.task.refresh_from_db()
        self.assertEqual(self.counts()["car"]["count"], 2)


class AnnotationCountsApiTest(_TaskFixture, APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.outsider = User.objects.create_user(username="outsider")
        self.make_task(self.owner)
        self.add_shape(self.car)
        self.add_shape(self.car, group=2, type="polygon")
        self.add_shape(self.car, group=2, type="polygon")

    def url(self, task_id=None):
        return f"/api/test/tasks/{task_id or self.task.id}/annotation-counts"

    def test_owner_gets_counts(self):
        with ForceLogin(self.owner, self.client):
            response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data["total"], 2)
        self.assertIsNone(response.data["group_by"])
        self.assertNotIn("by_type", response.data["labels"][0])

    def test_group_by_type(self):
        with ForceLogin(self.owner, self.client):
            response = self.client.get(self.url(), {"group_by": "type"})

        car = next(label for label in response.data["labels"] if label["name"] == "car")
        self.assertEqual(car["by_type"], {"rectangle": 1, "polygon": 1})

    def test_unknown_group_by_is_rejected(self):
        with ForceLogin(self.owner, self.client):
            response = self.client.get(self.url(), {"group_by": "label"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymous_is_refused(self):
        self.assertEqual(self.client.get(self.url()).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_without_access_is_refused(self):
        with ForceLogin(self.outsider, self.client):
            response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_assignee_gets_access(self):
        self.task.assignee = self.outsider
        self.task.save()

        with ForceLogin(self.outsider, self.client):
            response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_missing_task(self):
        with ForceLogin(self.owner, self.client):
            response = self.client.get(self.url(task_id=999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# The socket replays the HTTP request on another thread. With SQLite, an open test
# transaction would lock the tables it reads, so these tests commit for real.
class LiveAnnotationCountsTest(_TaskFixture, TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.outsider = User.objects.create_user(username="outsider")
        self.make_task(self.owner)

    async def open_socket(
        self, user: User, *, scheme="ws", origin=b"http://testserver", task_id=None
    ):
        await self.async_client.aforce_login(user)
        cookie = f"sessionid={self.async_client.cookies['sessionid'].value}".encode()
        scope = {
            "type": "websocket",
            "scheme": scheme,
            "path": f"/api/test/tasks/{task_id or self.task.id}/annotation-counts/ws",
            "raw_path": b"",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"host", b"testserver"), (b"origin", origin), (b"cookie", cookie)],
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 80),
        }
        socket = ApplicationCommunicator(route_websockets(get_asgi_application()), scope)
        await socket.send_input({"type": "websocket.connect"})
        return socket

    async def test_pushes_counts_on_connect_and_after_change(self):
        socket = await self.open_socket(self.owner)
        self.assertEqual((await socket.receive_output(5))["type"], "websocket.accept")
        first = json.loads((await socket.receive_output(5))["text"])
        self.assertEqual(first["total"], 0)

        await LabeledShape.objects.acreate(
            job=self.job, label=self.car, frame=0, type="rectangle", points=[0, 0]
        )
        task = await Task.objects.aget(id=self.task.id)
        await task.asave(update_fields=["updated_date"])  # what CVAT's annotation save does

        second = json.loads((await socket.receive_output(5))["text"])
        self.assertEqual(second["total"], 1)

        await socket.send_input({"type": "websocket.disconnect", "code": 1000})
        await socket.wait(5)

    async def test_refusal_closes_with_http_status(self):
        socket = await self.open_socket(self.outsider)
        self.assertEqual((await socket.receive_output(5))["type"], "websocket.accept")
        self.assertEqual(await socket.receive_output(5), {"type": "websocket.close", "code": 4403})
        await socket.wait(5)

    async def test_cross_site_origin_is_rejected_before_accept(self):
        socket = await self.open_socket(self.owner, origin=b"http://evil.example")
        self.assertEqual(await socket.receive_output(5), {"type": "websocket.close", "code": 4403})
        await socket.wait(5)

    async def test_origin_with_other_scheme_is_rejected(self):
        # Same host, but a plain-http page must not open the socket of an https server
        socket = await self.open_socket(self.owner, scheme="wss", origin=b"http://testserver")
        self.assertEqual(await socket.receive_output(5), {"type": "websocket.close", "code": 4403})
        await socket.wait(5)

    async def test_secure_origin_is_accepted_on_secure_socket(self):
        socket = await self.open_socket(self.owner, scheme="wss", origin=b"https://testserver")
        self.assertEqual((await socket.receive_output(5))["type"], "websocket.accept")

        await socket.send_input({"type": "websocket.disconnect", "code": 1000})
        await socket.wait(5)
