import { useState } from 'react';
import { Card, Description, Input, Label, Tag, TagGroup, TextArea, TextField } from '@heroui/react';
import { Hash } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { VideoDropZone } from '../../components/VideoDropZone';
import { normalizeHashtags } from '../../domain/publication/normalizeHashtags';
import type { AppDispatch, RootState } from '../../app/store';
import { setDescription, setHashtags, setTitle } from './composerSlice';

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
    </Card>
  );
}
