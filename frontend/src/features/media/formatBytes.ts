const MEGABYTE = 1024 ** 2;
const GIGABYTE = 1024 ** 3;

export function formatBytes(bytes: number, language: string): string {
  const [unit, value] =
    bytes >= GIGABYTE ? ['gigabyte', bytes / GIGABYTE] : ['megabyte', bytes / MEGABYTE];
  return new Intl.NumberFormat(language, { style: 'unit', unit, maximumFractionDigits: 1 }).format(
    value,
  );
}
