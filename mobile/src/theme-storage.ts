// Keep writes ordered, but report only the result of the latest selection.
export function createLatestThemeWriter(
  write: (id: string) => Promise<void>,
  onSettled: (saved: boolean) => void,
) {
  let queue = Promise.resolve();
  let latest = 0;
  return (id: string) => {
    const selection = ++latest;
    queue = queue.then(() => write(id)).then(
      () => { if (selection === latest) onSettled(true); },
      () => { if (selection === latest) onSettled(false); },
    );
    return queue;
  };
}
