import { useEffect, useState } from 'react';
import { Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { useDebouncedValue } from '../hooks/useDebouncedValue';

export default function SearchInput({ value = '', onSearch, delay = 300, ...rest }) {
  const [text, setText] = useState(value);
  const debounced = useDebouncedValue(text, delay);

  useEffect(() => { setText(value); }, [value]);
  useEffect(() => {
    if (debounced.trim() !== value.trim()) onSearch(debounced.trim());
  }, [debounced]);

  return (
    <Input
      allowClear
      prefix={<SearchOutlined aria-hidden />}
      value={text}
      onChange={(e) => {
        setText(e.target.value);
        if (!e.target.value) onSearch('');
      }}
      onPressEnter={() => onSearch(text.trim())}
      {...rest}
    />
  );
}
