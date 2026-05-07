interface LogoProps {
  variant?: "dark" | "light";
  className?: string;
  showSubtitle?: boolean;
}

export default function Logo({
  variant = "dark",
  className = "",
  showSubtitle = true,
}: LogoProps) {
  const color = variant === "dark" ? "#1A3C34" : "#FFFFFF";
  const subtitleColor =
    variant === "dark" ? "#1A3C34" : "rgba(255,255,255,0.9)";

  return (
    <svg
      viewBox="0 0 420 80"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="Carvalho & Furtado Advogados"
    >
      <text
        x="0"
        y="42"
        fontFamily="'Lexend Zetta', sans-serif"
        fontSize="34"
        fontWeight="500"
        letterSpacing="2"
        fill={color}
      >
        Carvalho
        <tspan fontWeight="400" fontSize="38" dx="4" dy="-1">
          &amp;
        </tspan>
        <tspan fontWeight="500" fontSize="34" dx="4" dy="1">
          Furtado
        </tspan>
      </text>
      {showSubtitle && (
        <text
          x="105"
          y="66"
          fontFamily="'Lexend Zetta', sans-serif"
          fontSize="13"
          fontWeight="400"
          letterSpacing="8"
          fill={subtitleColor}
        >
          ADVOGADOS
        </text>
      )}
    </svg>
  );
}
