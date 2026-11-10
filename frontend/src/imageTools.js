// imageTools.js - makes phone photos small before they are sent (a 5 MB photo becomes about 300 KB)

// Shrink a picture so its longest side is at most "maxSide" pixels. If anything goes wrong, the original is used.
export async function shrinkImage(file, maxSide = 1600, quality = 0.8) {
  if (!file.type || !file.type.startsWith('image/') || file.type === 'image/gif') return file
  try {
    const url = URL.createObjectURL(file)
    const image = await new Promise((resolve, reject) => {
      const picture = new Image()
      picture.onload = () => resolve(picture)
      picture.onerror = reject
      picture.src = url
    })
    URL.revokeObjectURL(url)
    const scale = Math.min(1, maxSide / Math.max(image.width, image.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(image.width * scale)
    canvas.height = Math.round(image.height * scale)
    canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
    if (!blob) return file
    return new File([blob], `${file.name.replace(/\.[^.]+$/, '') || 'photo'}.jpg`, { type: 'image/jpeg' })
  } catch {
    return file
  }
}