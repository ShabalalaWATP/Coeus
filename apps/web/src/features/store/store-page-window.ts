/**
 * First page, last page and a window around the current one, with gaps marked
 * by null. Keeps deep catalogues navigable without rendering hundreds of links.
 */
export function pageWindow(page: number, totalPages: number): (number | null)[] {
  if (!Number.isInteger(totalPages) || totalPages < 1) {
    return [];
  }
  const pages = new Set<number>([1, totalPages]);
  for (let offset = -1; offset <= 1; offset += 1) {
    const candidate = page + offset;
    if (Number.isInteger(candidate) && candidate >= 1 && candidate <= totalPages) {
      pages.add(candidate);
    }
  }
  const ordered = [...pages].sort((left, right) => left - right);
  const withGaps: (number | null)[] = [];
  let previous = 0;
  for (const entry of ordered) {
    if (previous !== 0 && entry - previous > 1) {
      withGaps.push(null);
    }
    withGaps.push(entry);
    previous = entry;
  }
  return withGaps;
}
