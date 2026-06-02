import React from 'react';
import { Card, Col, Row, Statistic } from 'antd';
import { Database, Activity, Server, FileText } from 'lucide-react';

interface DashboardStatsProps {
  kbCount: number;
  kbLoading: boolean;
  systemStatus: { text: string; color: string; desc: string };
}

export const DashboardStats: React.FC<DashboardStatsProps> = ({
  kbCount,
  kbLoading,
  systemStatus,
}) => {
  return (
    <Row gutter={[18, 18]}>
      {/* Metric 1: Total KB */}
      <Col xs={24} sm={12} lg={6}>
        <Card variant="borderless" hoverable className="glass-card">
          <Statistic
            title={<span className="font-outfit" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-secondary)' }}>Knowledge Bases</span>}
            value={kbCount}
            loading={kbLoading}
            prefix={<Database size={22} color="var(--accent-gradient)" style={{ marginRight: '8px', verticalAlign: 'middle' }} />}
            styles={{ content: { fontWeight: 800, fontSize: '28px', fontFamily: 'Outfit' } }}
          />
        </Card>
      </Col>

      {/* Metric 2: System Health */}
      <Col xs={24} sm={12} lg={6}>
        <Card variant="borderless" hoverable className="glass-card">
          <Statistic
            title={<span className="font-outfit" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-secondary)' }}>System Status</span>}
            value={systemStatus.text}
            prefix={<Activity size={22} color={systemStatus.color === 'green' ? '#10b981' : '#f59e0b'} style={{ marginRight: '8px', verticalAlign: 'middle' }} />}
            styles={{ content: { fontWeight: 800, fontSize: '24px', fontFamily: 'Outfit', color: systemStatus.color === 'green' ? '#10b981' : '#f59e0b' } }}
          />
        </Card>
      </Col>

      {/* Metric 3: Active Parser */}
      <Col xs={24} sm={12} lg={6}>
        <Card variant="borderless" hoverable className="glass-card">
          <Statistic
            title={<span className="font-outfit" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-secondary)' }}>Parser Engine</span>}
            value="Docling SDK"
            prefix={<Server size={22} color="#8b5cf6" style={{ marginRight: '8px', verticalAlign: 'middle' }} />}
            styles={{ content: { fontWeight: 800, fontSize: '24px', fontFamily: 'Outfit', color: '#8b5cf6' } }}
          />
        </Card>
      </Col>

      {/* Metric 4: Platform Version */}
      <Col xs={24} sm={12} lg={6}>
        <Card variant="borderless" hoverable className="glass-card">
          <Statistic
            title={<span className="font-outfit" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-secondary)' }}>Platform Version</span>}
            value="v0.1.0-alpha"
            prefix={<FileText size={22} color="#f59e0b" style={{ marginRight: '8px', verticalAlign: 'middle' }} />}
            styles={{ content: { fontWeight: 800, fontSize: '24px', fontFamily: 'Outfit' } }}
          />
        </Card>
      </Col>
    </Row>
  );
};
