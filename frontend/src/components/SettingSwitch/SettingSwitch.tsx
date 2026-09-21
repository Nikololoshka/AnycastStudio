import { Description, Label, Switch } from '@heroui/react';

export function SettingSwitch({
  label,
  description,
  isSelected,
  isDisabled,
  onChange,
}: {
  label: string;
  description?: string;
  isSelected: boolean;
  isDisabled?: boolean;
  onChange: (isSelected: boolean) => void;
}) {
  return (
    <Switch
      isSelected={isSelected}
      isDisabled={isDisabled}
      onChange={onChange}
      className="w-full py-1"
    >
      <Switch.Content className="flex w-full flex-row-reverse items-center justify-between gap-6">
        <Switch.Control>
          <Switch.Thumb />
        </Switch.Control>
        <span className="flex flex-col gap-0.5">
          <Label>{label}</Label>
          {description && <Description>{description}</Description>}
        </span>
      </Switch.Content>
    </Switch>
  );
}
