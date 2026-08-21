import Image from "next/image";

type PostPiloterLogoProps = {
  className?: string;
  priority?: boolean;
  alt?: string;
};

export function PostPiloterLogo({
  className = "h-8 w-auto",
  priority = false,
  alt = "PostPiloter",
}: PostPiloterLogoProps) {
  return (
    <Image
      src="/postpiloter-logo.png"
      alt={alt}
      width={1022}
      height={277}
      className={className}
      priority={priority}
      sizes="(max-width: 640px) 120px, 150px"
      draggable={false}
      data-brand-logo="postpiloter"
    />
  );
}
