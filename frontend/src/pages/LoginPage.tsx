import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { useAuth } from "../auth/AuthContext";
import { extractErrorMessage } from "../api/client";
import { APP_NAME, APP_NAME_FA } from "../appInfo";
import { AnimatedGridBackground } from "../components/AnimatedGridBackground";
import { BrandMark } from "../components/Brand";
import { Footer } from "../components/Footer";
import { PasswordInput } from "../ui/PasswordInput";
import { Button } from "../ui/Button";
import { PublicInfoLinks } from "../components/PublicInfoDialogs";
import { ThemeToggle } from "../ui/ThemeToggle";

interface PupilsProps {
  size?: number;
  maxDistance?: number;
  pupilColor?: string;
  forceLookX?: number;
  forceLookY?: number;
}

function Pupil({
  size = 12,
  maxDistance = 5,
  pupilColor = "#2D2D2D",
  forceLookX,
  forceLookY,
}: PupilsProps) {
  const [mouseX, setMouseX] = useState(0);
  const [mouseY, setMouseY] = useState(0);
  const pupilRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      setMouseX(event.clientX);
      setMouseY(event.clientY);
    };

    window.addEventListener("mousemove", handleMouseMove);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
    };
  }, []);

  const calculatePupilPosition = () => {
    if (!pupilRef.current) return { x: 0, y: 0 };

    if (forceLookX !== undefined && forceLookY !== undefined) {
      return { x: forceLookX, y: forceLookY };
    }

    const pupil = pupilRef.current.getBoundingClientRect();
    const pupilCenterX = pupil.left + pupil.width / 2;
    const pupilCenterY = pupil.top + pupil.height / 2;

    const deltaX = mouseX - pupilCenterX;
    const deltaY = mouseY - pupilCenterY;
    const distance = Math.min(Math.sqrt(deltaX ** 2 + deltaY ** 2), maxDistance);

    const angle = Math.atan2(deltaY, deltaX);
    const x = Math.cos(angle) * distance;
    const y = Math.sin(angle) * distance;

    return { x, y };
  };

  const pupilPosition = calculatePupilPosition();

  return (
    <div
      ref={pupilRef}
      className="rounded-full"
      style={{
        width: `${size}px`,
        height: `${size}px`,
        backgroundColor: pupilColor,
        transform: `translate(${pupilPosition.x}px, ${pupilPosition.y}px)`,
        transition: "transform 0.1s ease-out",
      }}
    />
  );
}

interface EyeBallProps {
  size?: number;
  pupilSize?: number;
  maxDistance?: number;
  eyeColor?: string;
  pupilColor?: string;
  isBlinking?: boolean;
  forceLookX?: number;
  forceLookY?: number;
}

function EyeBall({
  size = 48,
  pupilSize = 16,
  maxDistance = 10,
  eyeColor = "#FFFFFF",
  pupilColor = "#2D2D2D",
  isBlinking = false,
  forceLookX,
  forceLookY,
}: EyeBallProps) {
  const [mouseX, setMouseX] = useState(0);
  const [mouseY, setMouseY] = useState(0);
  const eyeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      setMouseX(event.clientX);
      setMouseY(event.clientY);
    };

    window.addEventListener("mousemove", handleMouseMove);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
    };
  }, []);

  const calculatePupilPosition = () => {
    if (!eyeRef.current) return { x: 0, y: 0 };

    if (forceLookX !== undefined && forceLookY !== undefined) {
      return { x: forceLookX, y: forceLookY };
    }

    const eye = eyeRef.current.getBoundingClientRect();
    const eyeCenterX = eye.left + eye.width / 2;
    const eyeCenterY = eye.top + eye.height / 2;

    const deltaX = mouseX - eyeCenterX;
    const deltaY = mouseY - eyeCenterY;
    const distance = Math.min(Math.sqrt(deltaX ** 2 + deltaY ** 2), maxDistance);

    const angle = Math.atan2(deltaY, deltaX);
    const x = Math.cos(angle) * distance;
    const y = Math.sin(angle) * distance;

    return { x, y };
  };

  const pupilPosition = calculatePupilPosition();

  return (
    <div
      ref={eyeRef}
      className="flex items-center justify-center rounded-full transition-all duration-150"
      style={{
        width: `${size}px`,
        height: isBlinking ? "2px" : `${size}px`,
        backgroundColor: eyeColor,
        overflow: "hidden",
      }}
    >
      {!isBlinking && (
        <div
          className="rounded-full"
          style={{
            width: `${pupilSize}px`,
            height: `${pupilSize}px`,
            backgroundColor: pupilColor,
            transform: `translate(${pupilPosition.x}px, ${pupilPosition.y}px)`,
            transition: "transform 0.1s ease-out",
          }}
        />
      )}
    </div>
  );
}

function AnimatedCharacterStage({
  showPassword,
  password,
  isTyping,
}: {
  showPassword: boolean;
  password: string;
  isTyping: boolean;
}) {
  const [mouseX, setMouseX] = useState(0);
  const [mouseY, setMouseY] = useState(0);
  const [isPurpleBlinking, setIsPurpleBlinking] = useState(false);
  const [isBlackBlinking, setIsBlackBlinking] = useState(false);
  const [isLookingAtEachOther, setIsLookingAtEachOther] = useState(false);
  const [isPurplePeeking, setIsPurplePeeking] = useState(false);
  const purpleRef = useRef<HTMLDivElement>(null);
  const blackRef = useRef<HTMLDivElement>(null);
  const yellowRef = useRef<HTMLDivElement>(null);
  const orangeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      setMouseX(event.clientX);
      setMouseY(event.clientY);
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  useEffect(() => {
    const getRandomBlinkInterval = () => Math.random() * 4000 + 3000;

    const scheduleBlink = () => {
      const blinkTimeout = setTimeout(() => {
        setIsPurpleBlinking(true);
        setTimeout(() => {
          setIsPurpleBlinking(false);
          scheduleBlink();
        }, 150);
      }, getRandomBlinkInterval());

      return blinkTimeout;
    };

    const timeout = scheduleBlink();
    return () => clearTimeout(timeout);
  }, []);

  useEffect(() => {
    const getRandomBlinkInterval = () => Math.random() * 4000 + 3000;

    const scheduleBlink = () => {
      const blinkTimeout = setTimeout(() => {
        setIsBlackBlinking(true);
        setTimeout(() => {
          setIsBlackBlinking(false);
          scheduleBlink();
        }, 150);
      }, getRandomBlinkInterval());

      return blinkTimeout;
    };

    const timeout = scheduleBlink();
    return () => clearTimeout(timeout);
  }, []);

  useEffect(() => {
    if (isTyping) {
      setIsLookingAtEachOther(true);
      const timer = setTimeout(() => {
        setIsLookingAtEachOther(false);
      }, 800);
      return () => clearTimeout(timer);
    }

    setIsLookingAtEachOther(false);
  }, [isTyping]);

  useEffect(() => {
    if (password.length > 0 && showPassword) {
      const schedulePeek = () => {
        const peekInterval = setTimeout(() => {
          setIsPurplePeeking(true);
          setTimeout(() => {
            setIsPurplePeeking(false);
          }, 800);
        }, Math.random() * 3000 + 2000);
        return peekInterval;
      };

      const firstPeek = schedulePeek();
      return () => clearTimeout(firstPeek);
    }

    setIsPurplePeeking(false);
  }, [password, showPassword]);

  const calculatePosition = (ref: RefObject<HTMLDivElement | null>) => {
    if (!ref.current) return { faceX: 0, faceY: 0, bodySkew: 0 };

    const rect = ref.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 3;

    const deltaX = mouseX - centerX;
    const deltaY = mouseY - centerY;

    const faceX = Math.max(-15, Math.min(15, deltaX / 20));
    const faceY = Math.max(-10, Math.min(10, deltaY / 30));
    const bodySkew = Math.max(-6, Math.min(6, -deltaX / 120));

    return { faceX, faceY, bodySkew };
  };

  const purplePos = calculatePosition(purpleRef);
  const blackPos = calculatePosition(blackRef);
  const yellowPos = calculatePosition(yellowRef);
  const orangePos = calculatePosition(orangeRef);

  return (
    <div className="relative h-[360px] w-full max-w-[560px] lg:h-[420px]">
      <div className="relative h-full w-full">
        <div
          ref={purpleRef}
          className="absolute bottom-0 transition-all duration-700 ease-in-out"
          style={{
            left: "70px",
            width: "180px",
            height: isTyping || (password.length > 0 && !showPassword) ? "440px" : "400px",
            backgroundColor: "#b61615",
            borderRadius: "10px 10px 0 0",
            zIndex: 1,
            transform:
              password.length > 0 && showPassword
                ? "skewX(0deg)"
                : isTyping || (password.length > 0 && !showPassword)
                  ? `skewX(${(purplePos.bodySkew || 0) - 12}deg) translateX(40px)`
                  : `skewX(${purplePos.bodySkew || 0}deg)`,
            transformOrigin: "bottom center",
          }}
        >
          <div
            className="absolute flex gap-8 transition-all duration-700 ease-in-out"
            style={{
              left: password.length > 0 && showPassword ? "20px" : isLookingAtEachOther ? "55px" : `${45 + purplePos.faceX}px`,
              top: password.length > 0 && showPassword ? "35px" : isLookingAtEachOther ? "65px" : `${40 + purplePos.faceY}px`,
            }}
          >
            <EyeBall
              size={18}
              pupilSize={7}
              maxDistance={5}
              eyeColor="white"
              pupilColor="#2D2D2D"
              isBlinking={isPurpleBlinking}
              forceLookX={password.length > 0 && showPassword ? (isPurplePeeking ? 4 : -4) : isLookingAtEachOther ? 3 : undefined}
              forceLookY={password.length > 0 && showPassword ? (isPurplePeeking ? 5 : -4) : isLookingAtEachOther ? 4 : undefined}
            />
            <EyeBall
              size={18}
              pupilSize={7}
              maxDistance={5}
              eyeColor="white"
              pupilColor="#2D2D2D"
              isBlinking={isPurpleBlinking}
              forceLookX={password.length > 0 && showPassword ? (isPurplePeeking ? 4 : -4) : isLookingAtEachOther ? 3 : undefined}
              forceLookY={password.length > 0 && showPassword ? (isPurplePeeking ? 5 : -4) : isLookingAtEachOther ? 4 : undefined}
            />
          </div>
        </div>

        <div
          ref={blackRef}
          className="absolute bottom-0 transition-all duration-700 ease-in-out"
          style={{
            left: "240px",
            width: "120px",
            height: "310px",
            backgroundColor: "#2D2D2D",
            borderRadius: "8px 8px 0 0",
            zIndex: 2,
            transform:
              password.length > 0 && showPassword
                ? "skewX(0deg)"
                : isLookingAtEachOther
                  ? `skewX(${(blackPos.bodySkew || 0) * 1.5 + 10}deg) translateX(20px)`
                  : isTyping || (password.length > 0 && !showPassword)
                    ? `skewX(${(blackPos.bodySkew || 0) * 1.5}deg)`
                    : `skewX(${blackPos.bodySkew || 0}deg)`,
            transformOrigin: "bottom center",
          }}
        >
          <div
            className="absolute flex gap-6 transition-all duration-700 ease-in-out"
            style={{
              left: password.length > 0 && showPassword ? "10px" : isLookingAtEachOther ? "32px" : `${26 + blackPos.faceX}px`,
              top: password.length > 0 && showPassword ? "28px" : isLookingAtEachOther ? "12px" : `${32 + blackPos.faceY}px`,
            }}
          >
            <EyeBall
              size={16}
              pupilSize={6}
              maxDistance={4}
              eyeColor="white"
              pupilColor="#2D2D2D"
              isBlinking={isBlackBlinking}
              forceLookX={password.length > 0 && showPassword ? -4 : isLookingAtEachOther ? 0 : undefined}
              forceLookY={password.length > 0 && showPassword ? -4 : isLookingAtEachOther ? -4 : undefined}
            />
            <EyeBall
              size={16}
              pupilSize={6}
              maxDistance={4}
              eyeColor="white"
              pupilColor="#2D2D2D"
              isBlinking={isBlackBlinking}
              forceLookX={password.length > 0 && showPassword ? -4 : isLookingAtEachOther ? 0 : undefined}
              forceLookY={password.length > 0 && showPassword ? -4 : isLookingAtEachOther ? -4 : undefined}
            />
          </div>
        </div>

        <div
          ref={orangeRef}
          className="absolute bottom-0 transition-all duration-700 ease-in-out"
          style={{
            left: "0px",
            width: "240px",
            height: "200px",
            zIndex: 3,
            backgroundColor: "#adadad",
            borderRadius: "120px 120px 0 0",
            transform: password.length > 0 && showPassword ? "skewX(0deg)" : `skewX(${orangePos.bodySkew || 0}deg)`,
            transformOrigin: "bottom center",
          }}
        >
          <div
            className="absolute flex gap-8 transition-all duration-200 ease-out"
            style={{
              left: password.length > 0 && showPassword ? "50px" : `${82 + (orangePos.faceX || 0)}px`,
              top: password.length > 0 && showPassword ? "85px" : `${90 + (orangePos.faceY || 0)}px`,
            }}
          >
            <Pupil size={12} maxDistance={5} pupilColor="#2D2D2D" forceLookX={password.length > 0 && showPassword ? -5 : undefined} forceLookY={password.length > 0 && showPassword ? -4 : undefined} />
            <Pupil size={12} maxDistance={5} pupilColor="#2D2D2D" forceLookX={password.length > 0 && showPassword ? -5 : undefined} forceLookY={password.length > 0 && showPassword ? -4 : undefined} />
          </div>
        </div>

        <div
          ref={yellowRef}
          className="absolute bottom-0 transition-all duration-700 ease-in-out"
          style={{
            left: "310px",
            width: "140px",
            height: "230px",
            backgroundColor: "#46ad9e",
            borderRadius: "70px 70px 0 0",
            zIndex: 4,
            transform: password.length > 0 && showPassword ? "skewX(0deg)" : `skewX(${yellowPos.bodySkew || 0}deg)`,
            transformOrigin: "bottom center",
          }}
        >
          <div
            className="absolute flex gap-6 transition-all duration-200 ease-out"
            style={{
              left: password.length > 0 && showPassword ? "20px" : `${52 + (yellowPos.faceX || 0)}px`,
              top: password.length > 0 && showPassword ? "35px" : `${40 + (yellowPos.faceY || 0)}px`,
            }}
          >
            <Pupil size={12} maxDistance={5} pupilColor="#2D2D2D" forceLookX={password.length > 0 && showPassword ? -5 : undefined} forceLookY={password.length > 0 && showPassword ? -4 : undefined} />
            <Pupil size={12} maxDistance={5} pupilColor="#2D2D2D" forceLookX={password.length > 0 && showPassword ? -5 : undefined} forceLookY={password.length > 0 && showPassword ? -4 : undefined} />
          </div>
          <div
            className="absolute h-[4px] w-20 rounded-full bg-[#2D2D2D] transition-all duration-200 ease-out"
            style={{
              left: password.length > 0 && showPassword ? "10px" : `${40 + (yellowPos.faceX || 0)}px`,
              top: password.length > 0 && showPassword ? "88px" : `${88 + (yellowPos.faceY || 0)}px`,
            }}
          />
        </div>
      </div>
    </div>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isTyping, setIsTyping] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden">
      <AnimatedGridBackground />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(191,191,191,1),transparent_38%),radial-gradient(circle_at_bottom_right,rgba(75,85,99,0.12),transparent_26%)]" />
      <div className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-5 lg:px-6">
        <div dir="ltr" className="grid flex-1 items-center gap-6 lg:grid-cols-[1.15fr_0.85fr] xl:gap-10">
          <motion.section
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.55, ease: "easeOut" }}
            className="relative hidden min-h-[620px] items-center justify-center overflow-hidden lg:flex"
          >
            <div className="w-full max-w-[580px] self-center">
              <AnimatedCharacterStage showPassword={showPassword} password={password} isTyping={isTyping} />
            </div>
          </motion.section>

          <motion.section
            dir="rtl"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.55, ease: "easeOut", delay: 0.05 }}
            className="flex items-center justify-center"
          >
            <div className="w-full max-w-md rounded-[28px] border border-white/80 bg-white/90 p-6 shadow-float backdrop-blur md:p-8">
              <div className="mb-8 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="rounded-2xl bg-pulse-50 p-3">
                    <BrandMark className="h-8 w-8" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-gray-900">{APP_NAME}</div>
                    <div className="text-xs font-medium text-gray-500">{APP_NAME_FA}</div>
                  </div>
                </div>
                <div className="rounded-full bg-pulse-50 px-3 py-1 text-[11px] font-semibold text-pulse-700">
                  Secure
                </div>
              </div>



              <motion.form
                onSubmit={handleSubmit}
                className="space-y-4"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, delay: 0.12 }}
              >
                <Field label="نام کاربری" htmlFor="login-username">
                  <input
                    id="login-username"
                    name="username"
                    required
                    autoComplete="username"
                    className="w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-gray-900 focus:bg-white"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    onFocus={() => setIsTyping(true)}
                    onBlur={() => setIsTyping(false)}
                    autoFocus
                  />
                </Field>

                <Field label="رمز عبور" htmlFor="login-password">
                  {/* همان ورودیِ رمزِ بقیهٔ سامانه — چشم در همان سمت و با همان
                      برچسب. نمایش این‌جا کنترل‌شده است چون شخصیت‌های صفحه هم
                      باید بدانند رمز پیداست یا نه (چشم‌هایشان را می‌پوشانند). */}
                  <PasswordInput
                    id="login-password"
                    name="password"
                    required
                    autoComplete="current-password"
                    baseClassName="w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 pl-11 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-gray-900 focus:bg-white"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onFocus={() => setIsTyping(true)}
                    onBlur={() => setIsTyping(false)}
                    visible={showPassword}
                    onVisibleChange={setShowPassword}
                  />
                </Field>

                {error && (
                  <motion.p
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className="rounded-2xl bg-red-50 px-3 py-2 text-sm text-red-600"
                  >
                    {error}
                  </motion.p>
                )}

                <Button type="submit" loading={submitting} className="w-full rounded-2xl">
                  {submitting ? "در حال ورود…" : "ورود"}
                </Button>
              </motion.form>
            </div>
          </motion.section>
        </div>

        <div className="mt-4 space-y-3">
          {/* انتخاب تم پیش از ورود هم لازم است: کسی که تم شب را می‌خواهد،
              نباید اول صفحهٔ روشنِ ورود را تحمل کند تا به کلیدِ داخل برنامه
              برسد. همین انتخاب ذخیره می‌شود و پس از ورود هم برجاست. */}
          <div className="flex justify-center">
            <ThemeToggle />
          </div>
          <PublicInfoLinks />
          <Footer />
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-gray-700">
        {label}
      </label>
      {children}
    </div>
  );
}
