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
import {
    Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

import { getCore } from 'cvat-core-wrapper';
import CVATLoadingSpinner from 'components/common/loading-spinner';
import GoBackButton from 'components/common/go-back-button';

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip);

const core = getCore();
const FALLBACK_COLOR = '#1890ff';

interface LabelCount {
    id: number;
    name: string;
    color: string;
    count: number;
}

interface AnnotationCounts {
    task_id: number;
    total: number;
    labels: LabelCount[];
}

async function fetchAnnotationCounts(taskId: number): Promise<AnnotationCounts> {
    const response = await core.server.request(
        `${core.config.backendAPI}/test/tasks/${taskId}/annotation-counts`,
        { method: 'GET' },
    );
    return response.data;
}

function AnnotationCountsChart({ labels }: { labels: LabelCount[] }): JSX.Element {
    const sorted = [...labels].sort((a, b) => b.count - a.count);
    return (
        <Bar
            options={{
                indexAxis: 'y',
                maintainAspectRatio: false,
                animation: false,
                plugins: { tooltip: { enabled: true } },
            }}
            data={{
                labels: sorted.map((label) => label.name),
                datasets: [{
                    label: 'Annotations',
                    data: sorted.map((label) => label.count),
                    backgroundColor: sorted.map((label) => label.color || FALLBACK_COLOR),
                }],
            }}
        />
    );
}

function AnnotationStatsPage(): JSX.Element {
    const { tid } = useParams<{ tid: string }>();
    const taskId = +tid;
    const [counts, setCounts] = useState<AnnotationCounts | null>(null);
    const [error, setError] = useState<Error | null>(null);
    const [fetching, setFetching] = useState(true);

    const load = useCallback(() => {
        setFetching(true);
        setError(null);
        fetchAnnotationCounts(taskId)
            .then(setCounts)
            .catch(setError)
            .finally(() => setFetching(false));
    }, [taskId]);

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
                <AnnotationCountsChart labels={counts.labels} />
            </div>
        );
    }

    return (
        <div className='cvat-annotation-stats-page'>
            <Row justify='center'>
                <Col span={22} xl={18} xxl={14}>
                    <GoBackButton />
                    <Title level={4}>{`Annotations per label, task #${taskId}`}</Title>
                    {counts && counts.total > 0 && (
                        <Text type='secondary'>
                            {`${counts.total} annotations across ${counts.labels.length} labels`}
                        </Text>
                    )}
                    {content}
                </Col>
            </Row>
        </div>
    );
}

export default React.memo(AnnotationStatsPage);
