// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './styles.scss';

import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router';
import { Row, Col } from 'antd/lib/grid';
import Title from 'antd/lib/typography/Title';
import Text from 'antd/lib/typography/Text';
import Button from 'antd/lib/button';
import Empty from 'antd/lib/empty';
import Result from 'antd/lib/result';
import Switch from 'antd/lib/switch';
import Space from 'antd/lib/space';
import {
    Chart as ChartJS, BarElement, CategoryScale, LinearScale, Legend, Tooltip,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

import { getCore } from 'cvat-core-wrapper';
import CVATLoadingSpinner from 'components/common/loading-spinner';
import GoBackButton from 'components/common/go-back-button';

ChartJS.register(BarElement, CategoryScale, LinearScale, Legend, Tooltip);

const core = getCore();
const FALLBACK_COLOR = '#1890ff';
const KIND_COLORS: Record<string, string> = {
    rectangle: '#1890ff',
    polygon: '#52c41a',
    mask: '#fa8c16',
    polyline: '#722ed1',
    points: '#eb2f96',
    ellipse: '#13c2c2',
    cuboid: '#a0d911',
    skeleton: '#2f54eb',
    track: '#faad14',
    tag: '#8c8c8c',
};

interface LabelCount {
    id: number;
    name: string;
    color: string;
    count: number;
    by_type?: Record<string, number>;
}

interface AnnotationCounts {
    task_id: number;
    total: number;
    group_by: 'type' | null;
    labels: LabelCount[];
}

async function fetchAnnotationCounts(taskId: number, groupByType: boolean): Promise<AnnotationCounts> {
    const response = await core.server.request(
        `${core.config.backendAPI}/test/tasks/${taskId}/annotation-counts`,
        { method: 'GET', params: groupByType ? { group_by: 'type' } : {} },
    ) as { data: AnnotationCounts };
    return response.data;
}

function AnnotationCountsChart({ counts }: { counts: AnnotationCounts }): JSX.Element {
    const sorted = [...counts.labels].sort((a, b) => b.count - a.count);
    const grouped = counts.group_by === 'type';
    const kinds = [...new Set(sorted.flatMap((label) => Object.keys(label.by_type ?? {})))];
    const datasets = grouped ? kinds.map((kind) => ({
        label: kind,
        data: sorted.map((label) => label.by_type?.[kind] ?? 0),
        backgroundColor: KIND_COLORS[kind] ?? FALLBACK_COLOR,
    })) : [{
        label: 'Annotations',
        data: sorted.map((label) => label.count),
        backgroundColor: sorted.map((label) => label.color || FALLBACK_COLOR),
    }];

    return (
        <Bar
            options={{
                indexAxis: 'y',
                maintainAspectRatio: false,
                animation: false,
                scales: { x: { stacked: grouped }, y: { stacked: grouped } },
                plugins: { legend: { display: grouped } },
            }}
            data={{ labels: sorted.map((label) => label.name), datasets }}
        />
    );
}

function AnnotationStatsPage(): JSX.Element {
    const { tid } = useParams<{ tid: string }>();
    const taskId = +tid;
    const [counts, setCounts] = useState<AnnotationCounts | null>(null);
    const [error, setError] = useState<Error | null>(null);
    const [fetching, setFetching] = useState(true);
    const [groupByType, setGroupByType] = useState(false);

    const load = useCallback(() => {
        setFetching(true);
        setError(null);
        fetchAnnotationCounts(taskId, groupByType)
            .then(setCounts)
            .catch(setError)
            .finally(() => setFetching(false));
    }, [taskId, groupByType]);

    useEffect(load, [load]);

    let content: JSX.Element;
    if (fetching && !counts) {
        content = <CVATLoadingSpinner />;
    } else if (error) {
        content = (
            <Result
                status='error'
                title='Could not load annotation counts'
                subTitle={error.message}
                extra={<Button type='primary' onClick={load}>Retry</Button>}
            />
        );
    } else if (!counts || counts.total === 0) {
        content = <Empty description='This task has no annotations yet' />;
    } else {
        content = (
            <div
                className='cvat-annotation-stats-chart'
                style={{ height: Math.max(300, counts.labels.length * 22) }}
            >
                <AnnotationCountsChart counts={counts} />
            </div>
        );
    }

    return (
        <div className='cvat-annotation-stats-page'>
            <Row justify='center'>
                <Col span={22} xl={18} xxl={14}>
                    <GoBackButton />
                    <Title level={4}>{`Annotations per label, task #${taskId}`}</Title>
                    <Space size='large'>
                        {counts && counts.total > 0 && (
                            <Text type='secondary'>
                                {`${counts.total} annotations across ${counts.labels.length} labels`}
                            </Text>
                        )}
                        <Space>
                            <Switch checked={groupByType} onChange={setGroupByType} />
                            <Text>Split by shape type</Text>
                        </Space>
                    </Space>
                    {content}
                </Col>
            </Row>
        </div>
    );
}

export default React.memo(AnnotationStatsPage);
