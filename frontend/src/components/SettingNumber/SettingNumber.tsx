import { Description, Label, NumberField } from '@heroui/react';

export function SettingNumber({
  label,
  description,
  value,
  minValue,
  step,
  onChange,
}: {
  label: string;
  description?: string;
  value: number;
  minValue?: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <NumberField
      value={value}
      minValue={minValue}
      step={step}
      onChange={(next) => onChange(Number.isNaN(next) ? (minValue ?? 0) : next)}
      fullWidth
      className="py-1"
    >
      <Label>{label}</Label>
      <NumberField.Group>
        <NumberField.DecrementButton />
        <NumberField.Input />
        <NumberField.IncrementButton />
      </NumberField.Group>
      {description && <Description>{description}</Description>}
    </NumberField>
  );
}
