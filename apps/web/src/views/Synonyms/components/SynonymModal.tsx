import React from 'react';
import { Modal, Form, Input, Select } from 'antd';
import type { FormInstance } from 'antd';
import type { SynonymMapRead } from '@/generated/api/types.gen';

interface SynonymModalProps {
  open: boolean;
  editingItem: SynonymMapRead | null;
  form: FormInstance;
  onOk: () => void;
  onCancel: () => void;
  confirmLoading: boolean;
}

export const SynonymModal: React.FC<SynonymModalProps> = ({
  open,
  editingItem,
  form,
  onOk,
  onCancel,
  confirmLoading,
}) => {
  return (
    <Modal
      title={
        <span className="font-outfit" style={{ fontSize: '18px', fontWeight: 800 }}>
          {editingItem ? 'Edit Synonym Mapping' : 'Register New Synonym Mapping'}
        </span>
      }
      open={open}
      onOk={onOk}
      onCancel={onCancel}
      confirmLoading={confirmLoading}
      okText={editingItem ? 'Update' : 'Register'}
      cancelText="Cancel"
      okButtonProps={{
        style: {
          background: 'linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%)',
          border: 'none',
          borderRadius: '8px',
          height: '36px',
          fontWeight: 600,
        },
      }}
      cancelButtonProps={{
        style: {
          borderRadius: '8px',
          height: '36px',
        },
      }}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        style={{ marginTop: '20px' }}
        initialValues={{ synonyms: [] }}
      >
        <Form.Item
          name="keyword"
          label={<strong style={{ fontSize: '13px' }}>Keyword / Abbreviation</strong>}
          rules={[
            { required: true, message: 'Please input the keyword!' },
            { max: 255, message: 'Keyword cannot exceed 255 characters.' },
          ]}
        >
          <Input
            placeholder="e.g. RAG, M-RAG, AI"
            disabled={!!editingItem} // Keyword is unique and immutable once created
            style={{ borderRadius: '8px', padding: '6px 12px' }}
          />
        </Form.Item>

        <Form.Item
          name="synonyms"
          label={
            <strong style={{ fontSize: '13px' }}>
              Synonyms
            </strong>
          }
          rules={[
            { required: true, message: 'Please enter at least one synonym!' },
            { type: 'array', min: 1, message: 'Please enter at least one synonym!' },
          ]}
        >
          <Select
            mode="tags"
            style={{ width: '100%' }}
            placeholder="Type a synonym and press Enter..."
            tokenSeparators={[',', ' ']}
            dropdownStyle={{ display: 'none' }} // Tags only input
          />
        </Form.Item>

        <Form.Item
          name="description"
          label={<strong style={{ fontSize: '13px' }}>Description (Optional)</strong>}
        >
          <Input.TextArea
            placeholder="Provide context on when this synonym mapping is applied..."
            rows={3}
            style={{ borderRadius: '8px' }}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
};
