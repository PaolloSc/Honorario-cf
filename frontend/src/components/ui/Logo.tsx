type LogoFormat = "horizontal" | "vertical" | "35";

interface LogoProps {
  variant?: "dark" | "light";
  format?: LogoFormat;
  className?: string;
  showSubtitle?: boolean;
}

export default function Logo({
  variant = "dark",
  format = "horizontal",
  className = "",
}: LogoProps) {
  const color = variant === "dark" ? "verde" : "bege";
  const src = `/brand/logo-${format}-${color}.png`;
  return (
    <img
      src={src}
      alt="Carvalho & Furtado Advogados"
      className={className}
    />
  );
}
