import React, { useState } from 'react';
import { Card, Input, Button, Space, Form, notification } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, BookOpen } from 'lucide-react';
import {
  getSynonymMapsApiV1SynonymsGet,
  createSynonymMapApiV1SynonymsPost,
  patchSynonymMapApiV1SynonymsSynonymIdPatch,
  deleteSynonymMapApiV1SynonymsSynonymIdDelete,
} from '@/generated/api/sdk.gen';
import { SynonymTable } from './components/SynonymTable';
import { SynonymModal } from './components/SynonymModal';
import type { SynonymMapRead } from '@/generated/api/types.gen';

export const Synonyms: React.FC = () => {
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const [searchText, setSearchText] = useState('');
  const [appliedSearchText, setAppliedSearchText] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<SynonymMapRead | null>(null);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // 1. Fetch Synonym Maps with React Query
  const { data: synonymData, isLoading } = useQuery({
    queryKey: ['synonymMaps', currentPage, pageSize, appliedSearchText],
    queryFn: () =>
      getSynonymMapsApiV1SynonymsGet({
        query: {
          offset: (currentPage - 1) * pageSize,
          limit: pageSize,
          search: appliedSearchText || undefined,
        },
        throwOnError: true,
      }),
  });

  // 2. Mutations
  const createMutation = useMutation({
    mutationFn: (data: { keyword: string; synonyms: string[]; description?: string }) =>
      createSynonymMapApiV1SynonymsPost({
        body: {
          keyword: data.keyword,
          synonyms: data.synonyms,
          description: data.description || null,
        },
        throwOnError: true,
      }),
    onSuccess: () => {
      notification.success({
        message: 'Successfully Registered',
        description: 'New synonym mapping was successfully registered.',
        placement: 'topRight',
      });
      queryClient.invalidateQueries({ queryKey: ['synonymMaps'] });
      closeModal();
    },
    onError: (error: Error) => {
      notification.error({
        message: 'Registration Failed',
        description: error.message || 'Failed to register the synonym.',
        placement: 'topRight',
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: { id: string; keyword?: string; synonyms?: string[]; description?: string }) =>
      patchSynonymMapApiV1SynonymsSynonymIdPatch({
        path: {
          synonym_id: data.id,
        },
        body: {
          keyword: data.keyword,
          synonyms: data.synonyms,
          description: data.description || null,
        },
        throwOnError: true,
      }),
    onSuccess: () => {
      notification.success({
        message: 'Successfully Updated',
        description: 'The synonym mapping was successfully updated.',
        placement: 'topRight',
      });
      queryClient.invalidateQueries({ queryKey: ['synonymMaps'] });
      closeModal();
    },
    onError: (error: Error) => {
      notification.error({
        message: 'Update Failed',
        description: error.message || 'Failed to update the synonym.',
        placement: 'topRight',
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      deleteSynonymMapApiV1SynonymsSynonymIdDelete({
        path: {
          synonym_id: id,
        },
        throwOnError: true,
      }),
    onSuccess: () => {
      notification.success({
        message: 'Successfully Deleted',
        description: 'The synonym mapping was successfully deleted.',
        placement: 'topRight',
      });
      queryClient.invalidateQueries({ queryKey: ['synonymMaps'] });
    },
    onError: (error: Error) => {
      notification.error({
        message: 'Deletion Failed',
        description: error.message || 'Failed to delete the synonym.',
        placement: 'topRight',
      });
    },
  });

  // Modal Handlers
  const openCreateModal = () => {
    setEditingItem(null);
    form.resetFields();
    setIsModalOpen(true);
  };

  const openEditModal = (item: SynonymMapRead) => {
    setEditingItem(item);
    form.setFieldsValue({
      keyword: item.keyword,
      synonyms: item.synonyms,
      description: item.description,
    });
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingItem(null);
    form.resetFields();
  };

  const handleSubmit = () => {
    form
      .validateFields()
      .then((values) => {
        if (editingItem) {
          updateMutation.mutate({
            id: editingItem.id,
            keyword: values.keyword,
            synonyms: values.synonyms,
            description: values.description,
          });
        } else {
          createMutation.mutate({
            keyword: values.keyword,
            synonyms: values.synonyms,
            description: values.description,
          });
        }
      })
      .catch((info) => {
        console.error('Validation Failed:', info);
      });
  };

  const items = synonymData?.data?.items || [];
  const totalItems = synonymData?.data?.total_count || 0;

  return (
    <div style={{ padding: '8px 0 24px 0' }}>
      <Card
        bordered={false}
        style={{
          borderRadius: '16px',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.05)',
        }}
      >
        {/* Header toolbar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '24px',
            flexWrap: 'wrap',
            gap: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                background: 'linear-gradient(135deg, #4f46e5 0%, #00f2fe 100%)',
                width: 44,
                height: 44,
                borderRadius: '12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 4px 14px rgba(79, 70, 229, 0.2)',
              }}
            >
              <BookOpen size={20} color="#fff" />
            </div>
            <div>
              <h3
                className="font-outfit"
                style={{ margin: 0, fontSize: '18px', fontWeight: 800 }}
              >
                Synonym Dictionary Maps
              </h3>
              <p style={{ margin: 0, fontSize: '12px', color: '#64748b' }}>
                Manage keyword mappings and abbreviation expansions to enrich retrieval context dynamically.
              </p>
            </div>
          </div>

          <Space size="middle">
            <Space.Compact style={{ width: 320 }}>
              <Input
                placeholder="Search synonyms..."
                prefix={<Search size={16} color="#94a3b8" />}
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                onPressEnter={() => {
                  setAppliedSearchText(searchText);
                  setCurrentPage(1);
                }}
                style={{
                  borderTopLeftRadius: '10px',
                  borderBottomLeftRadius: '10px',
                  padding: '6px 12px',
                }}
                allowClear
              />
              <Button
                type="primary"
                onClick={() => {
                  setAppliedSearchText(searchText);
                  setCurrentPage(1);
                }}
                style={{
                  borderTopRightRadius: '10px',
                  borderBottomRightRadius: '10px',
                  height: '38px',
                }}
              >
                Search
              </Button>
            </Space.Compact>
            <Button
              type="primary"
              icon={<Plus size={16} />}
              onClick={openCreateModal}
              style={{
                background: 'linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%)',
                border: 'none',
                height: '38px',
                borderRadius: '10px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              Add Synonym
            </Button>
          </Space>
        </div>

        {/* Synonym Table Component */}
        <SynonymTable
          loading={isLoading}
          dataSource={items}
          currentPage={currentPage}
          pageSize={pageSize}
          total={totalItems}
          onPageChange={(page, size) => {
            setCurrentPage(page);
            setPageSize(size);
          }}
          onEdit={openEditModal}
          onDelete={(id) => deleteMutation.mutate(id)}
          deletePending={deleteMutation.isPending}
        />
      </Card>

      {/* Synonym Modal Component */}
      <SynonymModal
        open={isModalOpen}
        editingItem={editingItem}
        form={form}
        onOk={handleSubmit}
        onCancel={closeModal}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      />
    </div>
  );
};
