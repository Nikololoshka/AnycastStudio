import { useState, type Key } from 'react';
import { Calendar, Card, DateField, DatePicker, Label, Tabs } from '@heroui/react';
import {
  getLocalTimeZone,
  now,
  parseAbsoluteToLocal,
  toCalendarDate,
  toCalendarDateTime,
  toTime,
  today,
  Time,
  type CalendarDate,
} from '@internationalized/date';
import { Zap } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { TimePicker } from '../../components/TimePicker';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { getCapabilitiesFor } from '../../platforms/registry';
import { TikTokConsent } from '../../platforms/tiktok';
import type { AvailablePlatform } from '../../domain/platform/order';
import type { AppDispatch, RootState } from '../../app/store';
import { setPublishAt } from './composerSlice';
import { usePublishablePlatforms } from './usePublishablePlatforms';

type ScheduleMode = 'now' | 'schedule';

function nextHour(): Time {
  const start = now(getLocalTimeZone()).add({ hours: 1 });
  return new Time(start.hour, 0);
}

function combine(date: CalendarDate, time: Time): string {
  return toCalendarDateTime(date, time).toDate(getLocalTimeZone()).toISOString();
}

function SchedulePlan() {
  const { t } = useTranslation('composer');
  const selectedPlatforms = usePublishablePlatforms();

  if (selectedPlatforms.length === 0) return null;

  const describe = (platform: AvailablePlatform) => {
    const { scheduling, label } = getCapabilitiesFor(platform);
    if (scheduling === 'native') return t('timing.nativePlan', { platform: label });
    if (scheduling === 'deferredUpload') return t('timing.deferredPlan', { platform: label });
    return t('timing.serverPlan', { platform: label });
  };

  return (
    <div className="flex flex-col gap-2 rounded-xl bg-surface-secondary px-4 py-3">
      <p className="text-sm font-medium">{t('timing.planTitle')}</p>
      <ul className="flex flex-col gap-1.5">
        {selectedPlatforms.map((platform) => (
          <li key={platform} className="flex items-start gap-2 text-xs text-muted">
            <PlatformGlyph platform={platform} size="sm" />
            <span>{describe(platform)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ComposerTimingCard() {
  const { t } = useTranslation('composer');
  const dispatch = useDispatch<AppDispatch>();
  const publishAt = useSelector((state: RootState) => state.composer.publishAt);
  const selectedPlatforms = usePublishablePlatforms();
  const [scheduleMode, setScheduleMode] = useState<ScheduleMode>(publishAt ? 'schedule' : 'now');

  const scheduled = publishAt ? parseAbsoluteToLocal(publishAt) : undefined;
  const [date, setDate] = useState<CalendarDate | null>(
    scheduled ? toCalendarDate(scheduled) : null,
  );
  const [time, setTime] = useState<Time | null>(scheduled ? toTime(scheduled) : null);
  const [isPast, setIsPast] = useState(false);

  function commitSchedule(nextDate: CalendarDate | null, nextTime: Time | null) {
    if (!nextDate) {
      setIsPast(false);
      dispatch(setPublishAt(undefined));
      return;
    }
    const moment = combine(nextDate, nextTime ?? nextHour());
    setIsPast(Date.parse(moment) <= Date.now());
    dispatch(setPublishAt(moment));
  }

  function changeScheduleMode(mode: ScheduleMode) {
    setScheduleMode(mode);
    if (mode === 'now') {
      setIsPast(false);
      dispatch(setPublishAt(undefined));
      return;
    }
    commitSchedule(date, time);
  }

  function changeDate(value: CalendarDate | null) {
    setDate(value);
    if (value && !time) setTime(nextHour());
    commitSchedule(value, time);
  }

  function changeTime(value: Time | null) {
    setTime(value);
    if (value) commitSchedule(date, value);
  }

  return (
    <Card className="gap-4 rounded-[14px] bg-surface p-5 shadow-surface">
      <h2 className="text-lg font-semibold">{t('sections.timing')}</h2>

      <Tabs
        selectedKey={scheduleMode}
        onSelectionChange={(key: Key) => changeScheduleMode(key as ScheduleMode)}
        className="gap-4"
      >
        <Tabs.ListContainer>
          <Tabs.List aria-label={t('timing.modeLabel')} className="grid w-full grid-cols-2">
            <Tabs.Tab id="now">
              {t('timing.now')}
              <Tabs.Indicator />
            </Tabs.Tab>
            <Tabs.Tab id="schedule">
              {t('timing.schedule')}
              <Tabs.Indicator />
            </Tabs.Tab>
          </Tabs.List>
        </Tabs.ListContainer>

        <Tabs.Panel id="now" className="p-0">
          <p className="flex items-center gap-2 text-sm text-muted">
            <Zap className="size-4" />
            {t('timing.immediate')}
          </p>
        </Tabs.Panel>

        <Tabs.Panel id="schedule" className="flex flex-col gap-3 p-0">
          <div className="grid grid-cols-2 items-start gap-3">
            <DatePicker minValue={today(getLocalTimeZone())} value={date} onChange={changeDate}>
              <Label>{t('timing.publishOn')}</Label>
              <DateField.Group fullWidth>
                <DateField.Input>
                  {(segment) => <DateField.Segment segment={segment} />}
                </DateField.Input>
                <DateField.Suffix>
                  <DatePicker.Trigger>
                    <DatePicker.TriggerIndicator />
                  </DatePicker.Trigger>
                </DateField.Suffix>
              </DateField.Group>
              <DatePicker.Popover>
                <Calendar aria-label={t('timing.calendarLabel')}>
                  <Calendar.Header>
                    <Calendar.YearPickerTrigger>
                      <Calendar.YearPickerTriggerHeading />
                      <Calendar.YearPickerTriggerIndicator />
                    </Calendar.YearPickerTrigger>
                    <Calendar.NavButton slot="previous" />
                    <Calendar.NavButton slot="next" />
                  </Calendar.Header>
                  <Calendar.Grid>
                    <Calendar.GridHeader>
                      {(day) => <Calendar.HeaderCell>{day}</Calendar.HeaderCell>}
                    </Calendar.GridHeader>
                    <Calendar.GridBody>{(day) => <Calendar.Cell date={day} />}</Calendar.GridBody>
                  </Calendar.Grid>
                  <Calendar.YearPickerGrid>
                    <Calendar.YearPickerGridBody>
                      {({ year }) => <Calendar.YearPickerCell year={year} />}
                    </Calendar.YearPickerGridBody>
                  </Calendar.YearPickerGrid>
                </Calendar>
              </DatePicker.Popover>
            </DatePicker>

            <TimePicker
              label={t('timing.publishAt')}
              slotsLabel={t('timing.timeSlotsLabel')}
              triggerLabel={t('timing.openTimeSlots')}
              value={time}
              onChange={changeTime}
            />
          </div>

          <p className="text-xs text-muted">{t('timing.timeZoneHint')}</p>
          {isPast && <p className="text-xs text-danger">{t('timing.pastTime')}</p>}

          <SchedulePlan />
        </Tabs.Panel>
      </Tabs>

      {selectedPlatforms.includes('tiktok') && <TikTokConsent />}
    </Card>
  );
}
