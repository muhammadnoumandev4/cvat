# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from rest_framework import serializers


class LabelCountSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    color = serializers.CharField()
    count = serializers.IntegerField()
    by_type = serializers.DictField(child=serializers.IntegerField(), required=False)


class AnnotationCountsSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()
    total = serializers.IntegerField()
    group_by = serializers.ChoiceField(choices=["type"], allow_null=True)
    labels = LabelCountSerializer(many=True)
