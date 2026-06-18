import React from 'react';
import { Table, Space, Tag, Tooltip, Button, Popconfirm } from 'antd';
import { Edit, Trash2 } from 'lucide-react';
import type { SynonymMapRead } from '@/generated/api/types.gen';

interface SynonymTableProps {
  loading: boolean;
  dataSource: SynonymMapRead[];
  currentPage: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number, size: number) => void;
  onEdit: (record: SynonymMapRead) => void;
  onDelete: (id: string) => void;
  deletePending: boolean;
}

export const SynonymTable: React.FC<SynonymTableProps> = ({
  loading,
  dataSource,
  currentPage,
  pageSize,
  total,
  onPageChange,
  onEdit,
  onDelete,
  deletePending,
}) => {
  const columns = [
    {
      title: <span className="font-outfit" style={{ fontWeight: 700 }}>Keyword (단어)</span>,
      dataIndex: 'keyword',
      key: 'keyword',
      width: '20%',
      render: (text: string) => (
        <Tag
          color="indigo"
          style={{
            fontSize: '14px',
            fontWeight: 700,
            padding: '4px 10px',
            borderRadius: '6px',
            fontFamily: 'Outfit, sans-serif',
          }}
        >
          {text}
        </Tag>
      ),
    },
    {
      title: <span className="font-outfit" style={{ fontWeight: 700 }}>Synonyms (동의어 목록)</span>,
      dataIndex: 'synonyms',
      key: 'synonyms',
      width: '45%',
      render: (synonyms: string[]) => (
        <Space size={[4, 8]} wrap>
          {synonyms.map((syn) => (
            <Tag
              key={syn}
              color="cyan"
              style={{
                fontSize: '13px',
                fontWeight: 500,
                padding: '2px 8px',
                borderRadius: '4px',
              }}
            >
              {syn}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: <span className="font-outfit" style={{ fontWeight: 700 }}>Description (설명)</span>,
      dataIndex: 'description',
      key: 'description',
      width: '20%',
      render: (text: string | null) => (
        <span style={{ color: '#64748b', fontSize: '13px' }}>
          {text || '-'}
        </span>
      ),
    },
    {
      title: <span className="font-outfit" style={{ fontWeight: 700, textAlign: 'right' }}>Actions</span>,
      key: 'actions',
      width: '15%',
      render: (_: unknown, record: SynonymMapRead) => (
        <Space size="middle" style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Tooltip title="Edit Synonym">
            <Button
              type="text"
              icon={<Edit size={16} color="#4f46e5" />}
              onClick={() => onEdit(record)}
            />
          </Tooltip>
          <Tooltip title="Delete Synonym">
            <Popconfirm
              title="Delete Synonym Map"
              description={`Are you sure you want to delete synonyms for "${record.keyword}"?`}
              onConfirm={() => onDelete(record.id)}
              okText="Delete"
              cancelText="Cancel"
              okButtonProps={{ danger: true, loading: deletePending }}
            >
              <Button
                type="text"
                danger
                icon={<Trash2 size={16} />}
              />
            </Popconfirm>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <Table
      loading={loading}
      columns={columns}
      dataSource={dataSource}
      rowKey="id"
      pagination={{
        current: currentPage,
        pageSize: pageSize,
        total: total,
        showSizeChanger: true,
        onChange: onPageChange,
        style: { marginTop: '20px' },
      }}
      style={{
        background: 'transparent',
      }}
    />
  );
};
