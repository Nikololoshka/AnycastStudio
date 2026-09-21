import { useMemo, useState } from 'react';
import { Button, Label, ListBox, Popover, TimeField } from '@heroui/react';
import { Time } from '@internationalized/date';
import { Clock } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const SLOT_STEP_MINUTES = 15;
const MINUTES_PER_DAY = 24 * 60;

function keyOf(time: Time): string {
  return `${String(time.hour).padStart(2, '0')}:${String(time.minute).padStart(2, '0')}`;
}

function timeOf(key: string): Time {
  const [hour, minute] = key.split(':').map(Number);
  return new Time(hour, minute);
}

export interface TimePickerProps {
  label: string;
  slotsLabel: string;
  triggerLabel: string;
  value: Time | null;
  onChange: (value: Time | null) => void;
  className?: string;
}

export function TimePicker({
  label,
  slotsLabel,
  triggerLabel,
  value,
  onChange,
  className = '',
}: TimePickerProps) {
  const { i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  const slots = useMemo(() => {
    const formatter = new Intl.DateTimeFormat(i18n.language, {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'UTC',
    });

    return Array.from({ length: MINUTES_PER_DAY / SLOT_STEP_MINUTES }, (_, index) => {
      const minutes = index * SLOT_STEP_MINUTES;
      const time = new Time(Math.floor(minutes / 60), minutes % 60);
      return {
        key: keyOf(time),
        label: formatter.format(new Date(Date.UTC(2000, 0, 1, time.hour, time.minute))),
      };
    });
  }, [i18n.language]);

  function selectSlot(key: string) {
    onChange(timeOf(key));
    setIsOpen(false);
  }

  return (
    <TimeField className={className} value={value} onChange={onChange}>
      <Label>{label}</Label>
      <TimeField.Group fullWidth>
        <TimeField.Input>{(segment) => <TimeField.Segment segment={segment} />}</TimeField.Input>
        <TimeField.Suffix>
          <Popover isOpen={isOpen} onOpenChange={setIsOpen}>
            <Button variant="ghost" size="sm" isIconOnly aria-label={triggerLabel}>
              <Clock className="size-4" />
            </Button>
            <Popover.Content placement="bottom end">
              <Popover.Dialog className="p-1">
                <ListBox
                  aria-label={slotsLabel}
                  selectionMode="single"
                  selectedKeys={value ? [keyOf(value)] : []}
                  onSelectionChange={(keys) => {
                    const [key] = [...keys];
                    if (typeof key === 'string') selectSlot(key);
                  }}
                  className="max-h-64 w-28 overflow-y-auto"
                >
                  {slots.map((slot) => (
                    <ListBox.Item key={slot.key} id={slot.key} textValue={slot.label}>
                      {slot.label}
                    </ListBox.Item>
                  ))}
                </ListBox>
              </Popover.Dialog>
            </Popover.Content>
          </Popover>
        </TimeField.Suffix>
      </TimeField.Group>
    </TimeField>
  );
}
