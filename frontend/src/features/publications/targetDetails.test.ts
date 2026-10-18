import type { TFunction } from 'i18next';
import { describe, expect, it } from 'vitest';
import { YOUTUBE_DEFAULT_SETTINGS } from '../../platforms/youtube/settings';
import { finalText, settingRows } from './targetDetails';

const t = ((key: string) => key) as unknown as TFunction<'platforms'>;
const publication = { title: 'Clip', description: 'About it', hashtags: ['meme', 'shorts'] };

describe('settingRows', () => {
  it('marks only the values that differ from the defaults', () => {
    const rows = settingRows('youtube', { privacyStatus: 'public' }, YOUTUBE_DEFAULT_SETTINGS, t);

    expect(rows.filter((row) => row.isChanged).map((row) => row.key)).toEqual(['privacyStatus']);
  });

  it('marks nothing while the defaults are unknown', () => {
    const rows = settingRows('youtube', { privacyStatus: 'public' }, undefined, t);

    expect(rows.some((row) => row.isChanged)).toBe(false);
  });

  it('labels choices by their option and lists switches last', () => {
    const rows = settingRows('youtube', {}, undefined, t);

    expect(rows[0]).toMatchObject({
      label: 'youtube.privacy.label',
      value: 'youtube.privacy.private',
    });
    expect(typeof rows[rows.length - 1].value).toBe('boolean');
  });
});

describe('finalText', () => {
  it('appends hashtags to the YouTube description when the setting is on', () => {
    expect(finalText('youtube', publication, {})).toEqual([
      { kind: 'title', text: 'Clip' },
      { kind: 'description', text: 'About it\n\n#meme #shorts' },
    ]);
  });

  it('leaves the YouTube description alone when the setting is off', () => {
    expect(finalText('youtube', publication, { hashtagsInDescription: false })[1].text).toBe(
      'About it',
    );
  });

  it('joins title, description and hashtags into one caption elsewhere', () => {
    expect(finalText('tiktok', publication, {})).toEqual([
      { kind: 'caption', text: 'Clip\n\nAbout it\n\n#meme #shorts' },
    ]);
  });
});
