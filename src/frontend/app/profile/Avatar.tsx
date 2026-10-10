import { useState } from 'react';
import type { AuthProfile } from '../auth';

export function Avatar({
  profile,
  size = 'small',
  preview,
}: {
  profile: AuthProfile;
  size?: 'small' | 'large';
  preview?: string;
}) {
  const src = preview || profile.avatar_url;
  const [failed, setFailed] = useState<string | null>(null);
  const initials =
    profile.name
      .trim()
      .split(/\s+/)
      .slice(-2)
      .map((part) => part[0])
      .join('')
      .toLocaleUpperCase() || '?';
  return (
    <span className={`profile-avatar profile-avatar-${size}`} aria-hidden="true">
      {src && failed !== src ? (
        <img src={src} alt="" referrerPolicy="no-referrer" onError={() => setFailed(src)} />
      ) : (
        initials
      )}
    </span>
  );
}

/** A tiny profile photo fits the existing 64 KB request limit; no original EXIF is uploaded. */
export async function prepareAvatar(file: File): Promise<string> {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024)
    throw new Error(
      'Chọn ảnh JPG, PNG hoặc WebP tối đa 5 MB. / Choose JPG, PNG or WebP up to 5 MB.',
    );
  const bitmap = await createImageBitmap(file);
  try {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 256;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Chưa xử lý được ảnh. / Unable to prepare this image.');
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, 256, 256);
    const edge = Math.min(bitmap.width, bitmap.height);
    ctx.drawImage(
      bitmap,
      (bitmap.width - edge) / 2,
      (bitmap.height - edge) / 2,
      edge,
      edge,
      0,
      0,
      256,
      256,
    );
    for (const quality of [0.85, 0.7, 0.55]) {
      const url = canvas.toDataURL('image/jpeg', quality);
      if (url.length < 53500) return url;
    }
    throw new Error('Chọn ảnh khác nhẹ hơn. / Choose a smaller image.');
  } finally {
    bitmap.close();
  }
}
