import {
  FolderOpen,
  House,
  Plug,
  Send,
  SquarePlus,
  type LucideIcon,
} from 'lucide-react';

interface NavItem {
  to: string;
  key: `nav.${'overview' | 'compose' | 'library' | 'publications' | 'platforms'}`;
  icon: LucideIcon;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: '/overview', key: 'nav.overview', icon: House },
  { to: '/compose', key: 'nav.compose', icon: SquarePlus },
  { to: '/library', key: 'nav.library', icon: FolderOpen },
  { to: '/publications', key: 'nav.publications', icon: Send },
  { to: '/platforms', key: 'nav.platforms', icon: Plug },
];
