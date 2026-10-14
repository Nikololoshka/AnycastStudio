import { PlatformGlyph } from '../../components/PlatformGlyph';
import { getLabelFor } from '../../platforms/registry';
import { DOT, type TargetMark } from './publicationMarks';

export function TargetMarks({ marks }: { marks: TargetMark[] }) {
  return (
    <span className="flex gap-2">
      {marks.map((mark) => (
        <span
          key={mark.platform}
          role="img"
          aria-label={`${getLabelFor(mark.platform)}: ${mark.status}`}
          title={`${getLabelFor(mark.platform)}: ${mark.status}`}
          className="relative"
        >
          <PlatformGlyph platform={mark.platform} size="sm" />
          <span
            className={`absolute -right-1 -bottom-1 size-2.5 rounded-full ring-2 ring-surface ${DOT[mark.tone]}`}
          />
        </span>
      ))}
    </span>
  );
}
