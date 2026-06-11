import React, { useState } from 'react';
import { Card, Button, Input, List, Empty, Modal } from 'antd';
import { Plus, Trash2, Database } from 'lucide-react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  getKnowledgeBasesApiV1KnowledgeBasesGet,
  createKnowledgeBaseApiV1KnowledgeBasesPost,
  deleteKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdDelete
} from '@/generated/api/sdk.gen';
import type { KnowledgeBaseRead } from '@/generated/api/types.gen';
import styles from './KnowledgeBaseList.module.css';

interface KnowledgeBaseListProps {
  selectedId: string | null;
  onSelect: (kb: KnowledgeBaseRead) => void;
  onDeleteSelected: () => void;
}

export const KnowledgeBaseList: React.FC<KnowledgeBaseListProps> = ({
  selectedId,
  onSelect,
  onDeleteSelected
}) => {
  const [newKbName, setNewKbName] = useState('');

  // 1. Fetch Knowledge Bases
  const { data: kbList, isLoading: kbLoading, refetch: refetchKbs } = useQuery({
    queryKey: ['kbList'],
    queryFn: () => getKnowledgeBasesApiV1KnowledgeBasesGet({ throwOnError: true }),
  });

  // 2. Create KB Mutation
  const createKbMutation = useMutation({
    mutationFn: (name: string) => {
      return createKnowledgeBaseApiV1KnowledgeBasesPost({
        body: { name },
        throwOnError: true,
      });
    },
    onSuccess: (response: { data?: KnowledgeBaseRead }) => {
      const created = response.data;
      if (created) {
        onSelect(created);
      }
      refetchKbs();
    },
    onError: (e) => {
      console.error('Failed to create knowledge base:', e);
      Modal.error({
        title: 'Failed to Create Knowledge Base',
        content: e instanceof Error ? e.message : 'Please check your connection.',
      });
    }
  });

  // 3. Delete KB Mutation
  const deleteKbMutation = useMutation({
    mutationFn: (kbId: string) => {
      return deleteKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdDelete({
        path: { knowledge_base_id: kbId },
        throwOnError: true,
      });
    },
    onSuccess: () => {
      refetchKbs();
      onDeleteSelected();
    },
    onError: (e) => {
      console.error('Failed to delete knowledge base:', e);
      Modal.error({
        title: 'Delete Failed',
        content: e instanceof Error ? e.message : 'Failed to delete the knowledge base.',
      });
    }
  });

  const handleCreateKb = () => {
    if (!newKbName.trim()) return;
    const name = newKbName.trim().toLowerCase().replace(/\s+/g, '_');
    createKbMutation.mutate(name);
    setNewKbName('');
  };

  const handleDeleteKb = (kbId: string, name: string) => {
    Modal.confirm({
      title: 'Delete Knowledge Base',
      content: `Are you sure you want to delete "${name}"? This will permanently delete all documents and parsed vectors inside it.`,
      okText: 'Yes, Delete',
      okType: 'danger',
      onOk: () => deleteKbMutation.mutate(kbId),
    });
  };

  // Auto-select the first KB if nothing is selected yet
  React.useEffect(() => {
    if (!selectedId && kbList?.data?.items?.length) {
      onSelect(kbList.data.items[0]);
    }
  }, [kbList, selectedId, onSelect]);

  return (
    <Card
      variant="borderless"
      className="glass-card"
      title={<span className="font-outfit" style={{ fontSize: '15px', fontWeight: 700 }}>Knowledge Bases</span>}
    >
      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        <Input
          placeholder="e.g. legal_docs"
          value={newKbName}
          onChange={(e) => setNewKbName(e.target.value)}
          onPressEnter={handleCreateKb}
          className="font-outfit"
        />
        <Button
          type="primary"
          icon={<Plus size={16} />}
          onClick={handleCreateKb}
          loading={createKbMutation.isPending}
        />
      </div>

      <List
        loading={kbLoading}
        dataSource={kbList?.data?.items || []}
        renderItem={(item: KnowledgeBaseRead) => (
          <List.Item
            className={`${styles.listItem} ${selectedId === item.id ? styles.selected : ''}`}
            onClick={() => onSelect(item)}
          >
            <div className={styles.itemWrapper}>
              <div className={styles.itemMeta}>
                <Database size={16} color={selectedId === item.id ? 'var(--accent-gradient)' : 'var(--text-secondary)'} />
                <span className="font-outfit" style={{ fontWeight: selectedId === item.id ? 700 : 500 }}>{item.name}</span>
              </div>
              <Button
                type="text"
                size="small"
                danger
                icon={<Trash2 size={14} />}
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteKb(item.id, item.name);
                }}
              />
            </div>
          </List.Item>
        )}
        locale={{
          emptyText: <Empty description="No bases found. Create one above!" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        }}
      />
    </Card>
  );
};
