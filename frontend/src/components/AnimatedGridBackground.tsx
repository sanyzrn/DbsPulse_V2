import { useEffect, useId, useRef, useState } from "react";
import { motion } from "motion/react";

interface Square {
  id: number;
  pos: [number, number];
}

interface AnimatedGridBackgroundProps {
  cellSize?: number;
  numSquares?: number;
  /** میزان کم‌رنگی مربع‌های چشمک‌زن (۰ تا ۱) */
  maxOpacity?: number;
  /** میزان کم‌رنگی خطوط ثابت گرید (۰ تا ۱) — مستقل از مربع‌ها */
  lineOpacity?: number;
  duration?: number;
}

export function AnimatedGridBackground({
  cellSize = 60,
  numSquares = 10,
  maxOpacity = 0.04,
  lineOpacity = 0.02,
  duration = 4,
}: AnimatedGridBackgroundProps) {
  const patternId = useId();
  const containerRef = useRef<SVGSVGElement | null>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [squares, setSquares] = useState<Square[]>([]);

  function getPos(): [number, number] {
    return [
      Math.floor((Math.random() * dimensions.width) / cellSize),
      Math.floor((Math.random() * dimensions.height) / cellSize),
    ];
  }

  function generateSquares(count: number): Square[] {
    return Array.from({ length: count }, (_, i) => ({
      id: i,
      pos: getPos(),
    }));
  }

  function updateSquarePosition(id: number) {
    setSquares((current) =>
      current.map((sq) => (sq.id === id ? { ...sq, pos: getPos() } : sq))
    );
  }

  useEffect(() => {
    if (dimensions.width && dimensions.height) {
      setSquares(generateSquares(numSquares));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dimensions, numSquares]);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    resizeObserver.observe(node);
    return () => resizeObserver.disconnect();
  }, []);

  return (
    <svg
      ref={containerRef}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 -z-10 h-full w-full text-pulse-60"
    >
      <defs>
        <pattern
          id={patternId}
          width={cellSize}
          height={cellSize}
          patternUnits="userSpaceOnUse"
          x={-1}
          y={-1}
        >
          <path
            d={`M.5 ${cellSize}V.5H${cellSize}`}
            fill="none"
            stroke="currentColor"
            strokeOpacity={lineOpacity}
          />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${patternId})`} />
      <svg x={-1} y={-1} className="overflow-visible">
        {squares.map(({ pos: [sx, sy], id }, index) => (
          <motion.rect
            key={`${sx}-${sy}-${index}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: maxOpacity }}
            transition={{
              duration,
              repeat: 1,
              delay: index * 0.1,
              repeatType: "reverse",
            }}
            onAnimationComplete={() => updateSquarePosition(id)}
            width={cellSize - 1}
            height={cellSize - 1}
            x={sx * cellSize + 1}
            y={sy * cellSize + 1}
            fill="currentColor"
            strokeWidth={0}
          />
        ))}
      </svg>
    </svg>
  );
}
