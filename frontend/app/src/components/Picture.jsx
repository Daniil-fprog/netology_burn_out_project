// Картинки: браузер берёт AVIF, если умеет, иначе WebP, иначе исходник.
// Размеры обязательны — чтобы место было зарезервировано до загрузки.
export default function Picture({ src, avif, webp, alt, width, height, eager = false, ...rest }) {
  const base = src.replace(/\.(png|jpe?g)$/i, '');
  return (
    <picture>
      <source type="image/avif" srcSet={avif ?? `${base}.avif`} />
      <source type="image/webp" srcSet={webp ?? `${base}.webp`} />
      <img
        src={src}
        alt={alt}
        width={width}
        height={height}
        loading={eager ? 'eager' : 'lazy'}
        decoding="async"
        {...rest}
      />
    </picture>
  );
}
