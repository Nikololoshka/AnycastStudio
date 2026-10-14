import { useState } from 'react';
import {
  Button,
  Card,
  Description,
  Input,
  Label,
  Tag,
  TagGroup,
  TextArea,
  TextField,
} from '@heroui/react';
import { Hash, ImagePlus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { VideoDropZone } from '../../components/VideoDropZone';
import { normalizeHashtags } from '../../domain/publication/normalizeHashtags';
import type { AppDispatch, RootState } from '../../app/store';
import { setDescription, setHashtags, setTitle } from './composerSlice';

const PLACEHOLDER_FRAMES = [
  'bg-muted-strong',
  'bg-muted',
  'bg-accent-soft-foreground',
  'bg-surface-tertiary',
];

export function ComposerFileCard() {
  const { t } = useTranslation('composer');

  return (
    <Card className="gap-4 rounded-[14px] bg-surface p-5 shadow-surface">
      <h2 className="text-lg font-semibold">{t('sections.video')}</h2>
      <VideoDropZone />
    </Card>
  );
}

export function ComposerTextCard() {
  const { t } = useTranslation('composer');
  const dispatch = useDispatch<AppDispatch>();
  const { title, description, hashtags } = useSelector((state: RootState) => state.composer);
  const [hashtagInput, setHashtagInput] = useState('');

  function commitHashtagInput() {
    if (!hashtagInput.trim()) return;
    dispatch(setHashtags(normalizeHashtags([...hashtags, hashtagInput].join(','))));
    setHashtagInput('');
  }

  function removeHashtags(tags: Set<unknown>) {
    dispatch(setHashtags(hashtags.filter((existing) => !tags.has(existing))));
  }

  return (
    <Card className="gap-5 rounded-[14px] bg-surface p-5 shadow-surface">
      <h2 className="text-lg font-semibold">{t('sections.text')}</h2>

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
        <TextArea rows={5} placeholder={t('text.descriptionPlaceholder')} />
        <Description className="text-right tabular-nums">
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

      <CoverPicker />
    </Card>
  );
}

function CoverPicker() {
  const { t } = useTranslation('composer');
  const thumbnail = useSelector((state: RootState) => state.composer.video?.thumbnailDataUrl);
  const [cover, setCover] = useState(0);

  return (
    <div role="group" aria-labelledby="composer-cover" className="flex flex-col gap-2">
      <span id="composer-cover" className="text-sm font-medium">
        {t('cover.label')}
      </span>
      <div className="flex flex-wrap gap-2.5">
        {PLACEHOLDER_FRAMES.map((background, index) => (
          <button
            key={background}
            type="button"
            aria-pressed={cover === index}
            aria-label={t('cover.frame', { number: index + 1 })}
            onClick={() => setCover(index)}
            className={`h-16 w-28 cursor-pointer overflow-hidden rounded-xl outline-none ring-offset-2 ring-offset-surface transition-shadow focus-visible:ring-2 focus-visible:ring-focus ${background} ${
              cover === index ? 'ring-3 ring-accent' : ''
            }`}
          >
            {index === 0 && thumbnail && (
              <img src={thumbnail} alt="" className="size-full object-cover" />
            )}
          </button>
        ))}
        <Button variant="secondary" isDisabled className="h-16 rounded-xl">
          <ImagePlus className="size-4" />
          {t('cover.custom')}
        </Button>
      </div>
    </div>
  );
}
