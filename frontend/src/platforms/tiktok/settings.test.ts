import { describe, expect, it } from 'vitest';
import {
  TIKTOK_DEFAULT_SETTINGS,
  tiktokCaptionOf,
  tiktokSettingErrors,
  tiktokSettingsOf,
  tiktokStoredSettingsOf,
} from './settings';

describe('tiktokCaptionOf', () => {
  it('joins the title, the description and the hashtags', () => {
    expect(tiktokCaptionOf('Title', 'About', ['one', 'two'])).toBe('Title\n\nAbout\n\n#one #two');
  });

  it('leaves no blank lines for empty parts', () => {
    expect(tiktokCaptionOf('Title', '  ', [])).toBe('Title');
  });

  it('counts an emoji as two units, as TikTok does', () => {
    expect(tiktokCaptionOf('😀', '', []).length).toBe(2);
  });
});

describe('tiktokSettingsOf', () => {
  it('keeps no privacy level when none was chosen', () => {
    expect(tiktokSettingsOf({})).toEqual(TIKTOK_DEFAULT_SETTINGS);
  });

  it('drops a privacy level TikTok does not know', () => {
    expect(tiktokSettingsOf({ privacyLevel: 'EVERYONE' }).privacyLevel).toBeNull();
  });

  it('turns a negative or non-numeric cover frame into the first frame', () => {
    expect(tiktokSettingsOf({ coverFrameSeconds: -3 }).coverFrameSeconds).toBe(0);
    expect(tiktokSettingsOf({ coverFrameSeconds: '3' }).coverFrameSeconds).toBe(0);
  });

  it('forgets the privacy level between sessions, so each post asks for it', () => {
    const stored = tiktokStoredSettingsOf({ privacyLevel: 'SELF_ONLY', disableDuet: true });
    expect(stored.privacyLevel).toBeNull();
    expect(stored.disableDuet).toBe(true);
  });
});

describe('tiktokSettingErrors', () => {
  const chosen = { ...TIKTOK_DEFAULT_SETTINGS, privacyLevel: 'SELF_ONLY' as const };

  it('asks for a privacy level', () => {
    expect(tiktokSettingErrors(TIKTOK_DEFAULT_SETTINGS)).toContain('privacyRequired');
  });

  it('asks whose content a disclosed post promotes', () => {
    expect(tiktokSettingErrors({ ...chosen, discloseContent: true })).toContain(
      'commercialContentUnspecified',
    );
  });

  it('refuses private branded content', () => {
    expect(tiktokSettingErrors({ ...chosen, discloseContent: true, brandContent: true })).toContain(
      'brandedContentCannotBePrivate',
    );
  });

  it('accepts a complete post', () => {
    expect(tiktokSettingErrors(chosen)).toEqual([]);
  });
});
