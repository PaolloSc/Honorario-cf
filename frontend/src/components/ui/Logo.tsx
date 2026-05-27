interface LogoProps {
  variant?: "dark" | "light";
  className?: string;
  showSubtitle?: boolean;
}

export default function Logo({
  variant = "dark",
  className = "",
}: LogoProps) {
  const src =
    variant === "dark"
      ? "/brand/logo-horizontal-verde.png"
      : "/brand/logo-horizontal-bege.png";
  return (
    <img
      src={src}
      alt="Carvalho & Furtado Advogados"
      className={className}
    />
  );
}
