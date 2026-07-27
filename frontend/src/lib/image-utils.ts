/** 이미지 전처리 — 큰 사진·미지원 형식을 업로드 가능한 JPEG 로 자동 변환.
 *
 *  실측(2026-07-27): 업로드 실패 신고의 원인은 서버가 아니라 입력 —
 *  아이폰·맥 사진은 5MB 를 넘거나 HEIC 라 서버 허용 형식(jpg/png/webp/gif,
 *  5MB)에 걸린다. 서버 한도를 올리는 대신(2GB 디스크) 클라에서 줄여 보낸다. */

const UPLOAD_MAX_BYTES = 5 * 1024 * 1024;
const ACCEPTED = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
]);
const MAX_DIMENSION = 2000;

export class UnsupportedImageError extends Error {
  constructor() {
    super("unsupported_image");
  }
}

/** 그대로 보낼 수 있으면 원본, 아니면 리사이즈 JPEG. 디코드 불가 시 UnsupportedImageError. */
export async function prepareImageForUpload(file: File): Promise<File> {
  if (ACCEPTED.has(file.type) && file.size <= UPLOAD_MAX_BYTES) {
    return file;
  }

  // 브라우저가 디코드할 수 있는 형식만 변환 가능 (HEIC 는 크롬 미지원 → 안내)
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new UnsupportedImageError();
  }

  const scale = Math.min(
    1,
    MAX_DIMENSION / Math.max(bitmap.width, bitmap.height),
  );
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bitmap.width * scale));
  canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new UnsupportedImageError();
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();

  // 품질을 단계적으로 낮춰 5MB 이하 보장
  for (const quality of [0.85, 0.7, 0.5]) {
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", quality),
    );
    if (blob && blob.size <= UPLOAD_MAX_BYTES) {
      return new File([blob], "image.jpg", { type: "image/jpeg" });
    }
  }
  throw new UnsupportedImageError();
}
