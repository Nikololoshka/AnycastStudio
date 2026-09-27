import { describe, expect, it } from 'vitest';
import {
  INSTAGRAM_DEFAULT_SETTINGS,
  hashtagCountOf,
  instagramCaptionErrors,
  instagramCaptionOf,
  instagramDurationErrors,
  instagramSettingsOf,
} from './settings';

describe('instagramCaptionOf', () => {
  it('joins the title, the description and the hashtags', () => {
    expect(instagramCaptionOf('Title', 'About', ['one', 'two'])).toBe(
      'Title\n\nAbout\n\n#one #two',
    );
  });

  it('leaves no blank lines for empty parts', () => {
    expect(instagramCaptionOf('', 'About', [])).toBe('About');
  });
});

describe('hashtagCountOf', () => {
  it('counts hashtags written in the description as well as the list', () => {
    expect(hashtagCountOf('Look #here\n\n#one #два')).toBe(3);
  });

  it('does not count a hash inside a word or a lone hash', () => {
    expect(hashtagCountOf('issue#12 # and ##double')).toBe(0);
  });
});

describe('instagramCaptionErrors', () => {
  it('allows thirty hashtags and refuses the thirty-first', () => {
    const tags = (count: number) => Array.from({ length: count }, (_, index) => `#t${index}`);
    expect(instagramCaptionErrors(tags(30).join(' '))).toEqual([]);
    expect(instagramCaptionErrors(tags(31).join(' '))).toEqual(['tooManyHashtags']);
  });

  it('refuses a caption over 2200 characters', () => {
    expect(instagramCaptionErrors('a'.repeat(2201))).toEqual(['captionTooLong']);
  });
});

describe('instagramDurationErrors', () => {
  it('refuses a reel shorter than three seconds or longer than fifteen minutes', () => {
    expect(instagramDurationErrors(2)).toEqual(['videoTooShort']);
    expect(instagramDurationErrors(15 * 60 + 1)).toEqual(['videoTooLong']);
    expect(instagramDurationErrors(30)).toEqual([]);
  });

  it('leaves an unknown duration to the server', () => {
    expect(instagramDurationErrors(undefined)).toEqual([]);
  });
});

describe('instagramSettingsOf', () => {
  it('shares to the feed by default', () => {
    expect(instagramSettingsOf({})).toEqual(INSTAGRAM_DEFAULT_SETTINGS);
  });

  it('keeps a choice not to share to the feed', () => {
    expect(instagramSettingsOf({ shareToFeed: false }).shareToFeed).toBe(false);
  });

  it('turns a negative or non-numeric cover frame into the first frame', () => {
    expect(instagramSettingsOf({ coverFrameSeconds: -3 }).coverFrameSeconds).toBe(0);
    expect(instagramSettingsOf({ coverFrameSeconds: '3' }).coverFrameSeconds).toBe(0);
  });
});
