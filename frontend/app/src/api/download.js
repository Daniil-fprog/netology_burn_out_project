// Скачивание файла, полученного из API как Blob.
export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Вызывает fn → Blob и сохраняет; ошибки показывает через message (App.useApp). */
export async function download(fn, filename, message) {
  const hide = message.loading('Готовим файл…', 0);
  try {
    const blob = await fn();
    saveBlob(blob, filename);
  } catch (e) {
    message.error(e.message);
  } finally {
    hide();
  }
}
