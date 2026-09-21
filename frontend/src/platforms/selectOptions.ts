import type { ParseKeys, TFunction } from 'i18next';
import type { SettingSelectOption } from '../components/SettingSelect';

export interface PlatformSelectOption<T extends string> {
  value: T;
  labelKey: ParseKeys<'platforms'>;
}

export function toSelectOptions<T extends string>(
  options: PlatformSelectOption<T>[],
  t: TFunction<'platforms'>,
): SettingSelectOption<T>[] {
  return options.map(({ value, labelKey }) => ({ value, label: t(labelKey) }));
}

export function oneOf<T extends string>(
  value: unknown,
  options: PlatformSelectOption<T>[],
  fallback: T,
): T {
  return options.some((option) => option.value === value) ? (value as T) : fallback;
}
