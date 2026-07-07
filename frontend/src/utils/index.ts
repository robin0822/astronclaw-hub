/**
 * 复制文本到剪贴板。
 * @param text 要复制的文本
 * @returns 是否复制成功
 */
export async function copyText(text: string): Promise<boolean> {
  try {
    // 使用现代的 Clipboard API
    await navigator.clipboard.writeText(text);

    return true;
  } catch {
    // 降级方案：如果 Clipboard API 不可用，使用传统方法
    const textarea = document.createElement('textarea');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
      return true;
    } catch (e) {
      console.error('复制失败：', e);
      return false;
    } finally {
      document.body.removeChild(textarea);
    }
  }
}

export function confirmDangerousAction(message: string): boolean {
  if (typeof window === 'undefined') return false;
  return window.confirm(message);
}
