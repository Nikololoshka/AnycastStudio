import { useState, type ReactNode } from 'react';
import {
  Calendar,
  DateField,
  DatePicker,
  Description,
  Input,
  Label,
  Radio,
  RadioGroup,
  Tag,
  TagGroup,
  TextArea,
  TextField,
} from '@heroui/react';
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
import { AnimatePresence, motion } from 'motion/react';
import { Hash } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { TimePicker } from '../../components/TimePicker';
import { VideoDropZone } from '../../components/VideoDropZone';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { getCapabilitiesFor } from '../../platforms/registry';
import type { AvailablePlatform } from '../../domain/platform/order';
import { normalizeHashtags } from '../../domain/publication/normalizeHashtags';
import type { AppDispatch, RootState } from '../../app/store';
import { setDescription, setHashtags, setPublishAt, setTitle } from './composerSlice';

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
  const selectedPlatforms = useSelector((state: RootState) => state.composer.selectedPlatforms);

  if (selectedPlatforms.length === 0) return null;

  const describe = (platform: AvailablePlatform) =>
    getCapabilitiesFor(platform).scheduling === 'native'
      ? t('timing.nativePlan', { platform: getCapabilitiesFor(platform).label })
      : t('timing.serverPlan', { platform: getCapabilitiesFor(platform).label });

  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-border bg-surface-secondary px-4 py-3">
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

function FormSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="font-display text-base font-semibold tracking-tight">{title}</h2>
      {children}
    </section>
  );
}

export function ComposerCommonTab() {
  const { t } = useTranslation('composer');
  const dispatch = useDispatch<AppDispatch>();
  const { title, description, hashtags, publishAt } = useSelector(
    (state: RootState) => state.composer,
  );
  const [hashtagInput, setHashtagInput] = useState('');
  const [scheduleMode, setScheduleMode] = useState<ScheduleMode>(publishAt ? 'schedule' : 'now');

  const scheduled = publishAt ? parseAbsoluteToLocal(publishAt) : undefined;
  const [date, setDate] = useState<CalendarDate | null>(
    scheduled ? toCalendarDate(scheduled) : null,
  );
  const [time, setTime] = useState<Time | null>(scheduled ? toTime(scheduled) : null);

  function commitHashtagInput() {
    if (!hashtagInput.trim()) return;
    dispatch(setHashtags(normalizeHashtags([...hashtags, hashtagInput].join(','))));
    setHashtagInput('');
  }

  function removeHashtags(tags: Set<unknown>) {
    dispatch(setHashtags(hashtags.filter((existing) => !tags.has(existing))));
  }

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
    <div className="flex flex-col gap-9">
      <FormSection title={t('sections.video')}>
        <VideoDropZone />
      </FormSection>

      <FormSection title={t('sections.text')}>
        <TextField value={title} onChange={(value) => dispatch(setTitle(value))} fullWidth>
          <Label>{t('text.titleLabel')}</Label>
          <Input placeholder={t('text.titlePlaceholder')} />
        </TextField>

        <TextField
          value={description}
          onChange={(value) => dispatch(setDescription(value))}
          fullWidth
        >
          <Label>{t('text.descriptionLabel')}</Label>
          <TextArea rows={4} placeholder={t('text.descriptionPlaceholder')} />
          <Description className="tabular-nums">
            {t('text.characterCount', { count: description.length })}
          </Description>
        </TextField>

        <div className="flex flex-col gap-2">
          <TextField value={hashtagInput} onChange={setHashtagInput} fullWidth>
            <Label>{t('text.hashtagsLabel')}</Label>
            <Input
              placeholder={t('text.hashtagsPlaceholder')}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  commitHashtagInput();
                }
              }}
              onBlur={commitHashtagInput}
            />
            <Description>{t('text.hashtagsHint')}</Description>
          </TextField>
          {hashtags.length > 0 && (
            <TagGroup aria-label={t('text.hashtagsLabel')} onRemove={removeHashtags} size="sm">
              <TagGroup.List className="flex flex-wrap gap-1.5">
                {hashtags.map((tag) => (
                  <Tag key={tag} id={tag} textValue={tag}>
                    <Hash className="size-3 text-muted" />
                    {tag}
                  </Tag>
                ))}
              </TagGroup.List>
            </TagGroup>
          )}
        </div>
      </FormSection>

      <FormSection title={t('sections.timing')}>
        <RadioGroup
          value={scheduleMode}
          onChange={(value) => changeScheduleMode(value as ScheduleMode)}
          orientation="horizontal"
          aria-label={t('timing.modeLabel')}
          className="flex flex-row gap-6"
        >
          <Radio value="now">
            <Radio.Content>
              <Radio.Control>
                <Radio.Indicator />
              </Radio.Control>
              {t('timing.now')}
            </Radio.Content>
          </Radio>
          <Radio value="schedule">
            <Radio.Content>
              <Radio.Control>
                <Radio.Indicator />
              </Radio.Control>
              {t('timing.schedule')}
            </Radio.Content>
          </Radio>
        </RadioGroup>

        <AnimatePresence initial={false}>
          {scheduleMode === 'schedule' && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="flex flex-wrap items-start gap-3">
                <DatePicker
                  className="w-52"
                  minValue={today(getLocalTimeZone())}
                  value={date}
                  onChange={changeDate}
                >
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
                        <Calendar.GridBody>
                          {(day) => <Calendar.Cell date={day} />}
                        </Calendar.GridBody>
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
                  className="w-32"
                  label={t('timing.publishAt')}
                  slotsLabel={t('timing.timeSlotsLabel')}
                  triggerLabel={t('timing.openTimeSlots')}
                  value={time}
                  onChange={changeTime}
                />
              </div>

              <p className="pt-2 text-xs text-muted">{t('timing.timeZoneHint')}</p>

              {isPast && <p className="pt-1 text-xs text-danger">{t('timing.pastTime')}</p>}

              <div className="pt-4">
                <SchedulePlan />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </FormSection>
    </div>
  );
}
