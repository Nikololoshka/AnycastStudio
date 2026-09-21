import { Description, Label, ListBox, Select } from '@heroui/react';

export interface SettingSelectOption<T extends string> {
  value: T;
  label: string;
}

export function SettingSelect<T extends string>({
  label,
  description,
  value,
  options,
  isDisabled,
  onChange,
}: {
  label: string;
  description?: string;
  value: T;
  options: SettingSelectOption<T>[];
  isDisabled?: boolean;
  onChange: (value: T) => void;
}) {
  return (
    <Select
      selectedKey={value}
      isDisabled={isDisabled}
      onSelectionChange={(key) => onChange(key as T)}
      fullWidth
      className="py-1"
    >
      <Label>{label}</Label>
      <Select.Trigger>
        <Select.Value />
        <Select.Indicator />
      </Select.Trigger>
      {description && <Description>{description}</Description>}
      <Select.Popover>
        <ListBox>
          {options.map((option) => (
            <ListBox.Item key={option.value} id={option.value} textValue={option.label}>
              {option.label}
            </ListBox.Item>
          ))}
        </ListBox>
      </Select.Popover>
    </Select>
  );
}
