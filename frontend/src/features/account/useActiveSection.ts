import { useEffect, useState, type RefObject } from 'react';

const READING_BAND = '-88px 0px -55% 0px';

export function useActiveSection<T extends string>(
  ids: readonly T[],
  initial: T,
  endRef: RefObject<HTMLElement | null>,
): T {
  const [active, setActive] = useState(initial);

  useEffect(() => {
    const visible = new Set<string>();
    let atEnd = false;

    const pick = () =>
      setActive((current) =>
        atEnd ? ids[ids.length - 1] : (ids.find((id) => visible.has(id)) ?? current),
      );

    const band = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) visible.add(entry.target.id);
          else visible.delete(entry.target.id);
        }
        pick();
      },
      { rootMargin: READING_BAND },
    );
    const end = new IntersectionObserver(([entry]) => {
      atEnd = entry.isIntersecting;
      pick();
    });

    for (const id of ids) {
      const section = document.getElementById(id);
      if (section) band.observe(section);
    }
    if (endRef.current) end.observe(endRef.current);

    return () => {
      band.disconnect();
      end.disconnect();
    };
  }, [ids, endRef]);

  return active;
}
