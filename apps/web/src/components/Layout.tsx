import React, { useState } from 'react';
import { Layout as AntdLayout, Menu, Button, Space, Badge, Tooltip } from 'antd';
import { useThemeStore } from '../stores/themeStore';
import {
  LayoutDashboard,
  Database,
  Sun,
  Moon,
  Server,
  RefreshCw,
  FileText,
  Menu as MenuIcon,
  MessageSquare,
  GitMerge,
  BookOpen,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { healthApiHealthGet } from '../generated/api/sdk.gen';

const { Sider, Content, Header } = AntdLayout;

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { isDarkMode, activeTab, toggleDarkMode, setActiveTab } = useThemeStore();
  const [collapsed, setCollapsed] = useState(false);

  // Poll backend health status every 5 seconds
  const { data: healthData, isError, refetch, isFetching } = useQuery({
    queryKey: ['apiHealth'],
    queryFn: () => healthApiHealthGet({ throwOnError: true }),
    refetchInterval: 5000,
    retry: 1,
  });

  const getHealthStatus = () => {
    if (isError) return { status: 'error' as const, text: 'Offline' };
    if (!healthData) return { status: 'warning' as const, text: 'Connecting' };
    const res = healthData?.data as { status?: string; success?: boolean } | null | undefined;
    if (res?.status === 'healthy' || res?.success || res?.status === 'ok') {
      return { status: 'success' as const, text: 'Online' };
    }
    return { status: 'warning' as const, text: 'Degraded' };
  };

  const health = getHealthStatus();

  const menuItems = [
    {
      key: 'dashboard',
      icon: <LayoutDashboard size={18} />,
      label: <span className="font-outfit" style={{ fontSize: '15px', fontWeight: 500 }}>Dashboard</span>,
    },
    {
      key: 'knowledge',
      icon: <Database size={18} />,
      label: <span className="font-outfit" style={{ fontSize: '15px', fontWeight: 500 }}>Knowledge Bases</span>,
    },
    {
      key: 'playground',
      icon: <GitMerge size={18} />,
      label: <span className="font-outfit" style={{ fontSize: '15px', fontWeight: 500 }}>Playground</span>,
    },
    {
      key: 'workbench',
      icon: <FileText size={18} />,
      label: <span className="font-outfit" style={{ fontSize: '15px', fontWeight: 500 }}>Showcase Workbench</span>,
    },
    {
      key: 'chat',
      icon: <MessageSquare size={18} />,
      label: <span className="font-outfit" style={{ fontSize: '15px', fontWeight: 500 }}>Agent Chat</span>,
    },
    {
      key: 'providers',
      icon: <Server size={18} />,
      label: <span className="font-outfit" style={{ fontSize: '15px', fontWeight: 500 }}>Providers & Models</span>,
    },
    {
      key: 'synonyms',
      icon: <BookOpen size={18} />,
      label: <span className="font-outfit" style={{ fontSize: '15px', fontWeight: 500 }}>Synonym Dictionary</span>,
    },
  ];

  return (
    <AntdLayout style={{ minHeight: '100vh', background: 'var(--bg-app, #f6f7f9)' }}>
      {/* Sidebar Panel */}
      <Sider
        width={260}
        collapsedWidth={0}
        collapsed={collapsed}
        trigger={null}
        style={{
          position: 'fixed',
          left: collapsed ? -260 : 0,
          top: 0,
          bottom: 0,
          height: '100vh',
          zIndex: 10,
          borderRight: collapsed ? 'none' : '1px solid var(--border-color, #dde3ea)',
          background: isDarkMode ? '#111827' : '#ffffff',
          overflow: 'hidden',
          transition: 'all 0.2s ease-in-out',
        }}
      >
        {/* Brand Logo */}
        <div style={{ padding: '24px 20px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              background: 'linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%)',
              width: 38,
              height: 38,
              borderRadius: '10px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(79, 70, 229, 0.25)',
            }}
          >
            <Server size={20} color="#fff" />
          </div>
          <div>
            <h1
              className="font-outfit"
              style={{
                margin: 0,
                fontSize: '18px',
                lineHeight: '1.2',
                fontWeight: 800,
                color: isDarkMode ? '#f3f4f6' : '#111827',
              }}
            >
              RAG PROVING
            </h1>
            <p className="font-outfit" style={{ margin: 0, fontSize: '11px', color: '#6b7280', fontWeight: 600, letterSpacing: '0.05em' }}>
              GROUND ENGINE
            </p>
          </div>
        </div>

        {/* Sidebar Menu */}
        <Menu
          mode="inline"
          selectedKeys={[activeTab]}
          onClick={({ key }) => setActiveTab(key)}
          items={menuItems}
          style={{
            background: 'transparent',
            borderRight: 0,
            padding: '12px 10px',
          }}
        />

        {/* System Health Panel */}
        <div
          style={{
            position: 'absolute',
            bottom: 24,
            left: 16,
            right: 16,
            padding: '16px',
            borderRadius: '12px',
            border: '1px solid var(--border-color, #e5e7eb)',
            background: isDarkMode ? '#1f2937' : '#f9fafb',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#6b7280' }}>System API Status</span>
            <Tooltip title="Force Refresh">
              <Button
                type="text"
                size="small"
                icon={<RefreshCw size={12} className={isFetching ? 'glow-active' : ''} />}
                onClick={() => refetch()}
              />
            </Tooltip>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Badge status={health.status} />
            <span className="font-outfit" style={{ fontSize: '14px', fontWeight: 700 }}>
              {health.text}
            </span>
          </div>
        </div>
      </Sider>

      {/* Main Container */}
      <AntdLayout style={{
        marginLeft: collapsed ? 0 : 260,
        height: '100vh',
        overflow: 'hidden',
        background: 'transparent',
        transition: 'margin-left 0.2s ease-in-out'
      }}>
        {/* Header Section */}
        <Header
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 9,
            width: '100%',
            height: '70px',
            padding: '0 32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: isDarkMode ? '#111827' : '#ffffff',
            borderBottom: '1px solid var(--border-color, #dde3ea)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <Button
              type="text"
              icon={<MenuIcon size={20} />}
              onClick={() => setCollapsed(!collapsed)}
              style={{
                width: 40,
                height: 40,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '1px solid var(--border-color, #dde3ea)',
                background: isDarkMode ? '#1f2937' : '#ffffff',
              }}
              title={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
            />
            <h2 className="font-outfit" style={{ margin: 0, fontSize: '20px', fontWeight: 700, textTransform: 'capitalize' }}>
              {activeTab === 'knowledge'
                ? 'Knowledge Base Management'
                : activeTab === 'playground'
                  ? 'Retrieval Playground'
                : activeTab === 'workbench'
                  ? 'Showcase Workbench'
                : activeTab === 'chat'
                  ? 'Agent Chat Proving'
                : activeTab === 'providers'
                  ? 'Providers & Models Registry'
                : activeTab === 'synonyms'
                  ? 'Synonym Dictionary Admin'
                  : 'Dashboard Overview'}
            </h2>
          </div>

          <Space size="middle">
            {/* Theme Toggle Button */}
            <Tooltip title={isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}>
              <Button
                type="text"
                shape="circle"
                icon={isDarkMode ? <Sun size={20} color="#eab308" /> : <Moon size={20} color="#4f46e5" />}
                onClick={toggleDarkMode}
                style={{
                  width: 42,
                  height: 42,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: '1px solid var(--border-color, #dde3ea)',
                  background: isDarkMode ? '#1f2937' : '#ffffff',
                }}
              />
            </Tooltip>
          </Space>
        </Header>

        {/* Content Area */}
        <Content style={{ padding: '32px', height: 'calc(100vh - 70px)', overflowY: 'auto' }}>
          <div style={{ maxWidth: activeTab === 'dashboard' ? 1400 : '100%', margin: '0 auto', height: '100%' }}>
            {children}
          </div>
        </Content>
      </AntdLayout>
    </AntdLayout>
  );
};
