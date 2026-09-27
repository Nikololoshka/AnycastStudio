import { describe, expect, it } from 'vitest';
import {
  X_DEFAULT_SETTINGS,
  xCaptionErrors,
  xCaptionOf,
  xDurationErrors,
  xSettingsOf,
} from './settings';

describe('xCaptionOf', () => {
  it('joins the title, the description and the hashtags', () => {
    expect(xCaptionOf('Title', 'About', ['one', 'two'])).toBe('Title\n\nAbout\n\n#one #two');
  });

  it('leaves no blank lines for empty parts', () => {
    expect(xCaptionOf('Title', '  ', [])).toBe('Title');
  });
});

describe('xCaptionErrors', () => {
  it('allows 280 characters and refuses the 281st', () => {
    expect(xCaptionErrors('a'.repeat(280))).toEqual([]);
    expect(xCaptionErrors('a'.repeat(281))).toEqual(['captionTooLong']);
  });

  it('counts an emoji as two, as the server does', () => {
    expect(xCaptionErrors('😀'.repeat(140))).toEqual([]);
    expect(xCaptionErrors('😀'.repeat(141))).toEqual(['captionTooLong']);
  });
});

describe('xDurationErrors', () => {
  it('refuses a video shorter than half a second or longer than 140 seconds', () => {
    expect(xDurationErrors(0.4)).toEqual(['videoTooShort']);
    expect(xDurationErrors(140.5)).toEqual(['videoTooLong']);
    expect(xDurationErrors(140)).toEqual([]);
  });

  it('leaves an unknown duration to the server', () => {
    expect(xDurationErrors(undefined)).toEqual([]);
  });
});

describe('xSettingsOf', () => {
  it('lets everyone reply and discloses nothing by default', () => {
    expect(xSettingsOf({})).toEqual(X_DEFAULT_SETTINGS);
  });

  it('falls back to everyone for an unknown reply audience', () => {
    expect(xSettingsOf({ replyAudience: 'friends' }).replyAudience).toBe('everyone');
  });

  it('keeps a chosen audience and disclosures', () => {
    const settings = xSettingsOf({
      replyAudience: 'verified',
      madeWithAi: true,
      paidPartnership: 'yes',
    });
    expect(settings).toEqual({
      ...X_DEFAULT_SETTINGS,
      replyAudience: 'verified',
      madeWithAi: true,
    });
  });
});
