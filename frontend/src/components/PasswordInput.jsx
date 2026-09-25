import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useApp } from "@/context/AppContext";
import { cn } from "@/lib/utils";

export const PasswordInput = ({ className, wrapperClassName, "data-testid": tid, ...props }) => {
  const [show, setShow] = useState(false);
  const { t } = useApp();
  const label = t(show ? "hide_password" : "show_password");
  return (
    <div className={cn("relative", wrapperClassName)}>
      <Input {...props} type={show ? "text" : "password"} data-testid={tid} className={cn(className, "mt-0 pr-10")} />
      <button type="button" onClick={() => setShow((s) => !s)} aria-label={label} title={label} aria-pressed={show} data-testid={`${tid}-toggle`}
        className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-slate-400 transition-colors duration-150 hover:bg-slate-100 hover:text-[#00A878] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00A878]/40">
        {show ? <EyeOff className="h-4 w-4" strokeWidth={1.8} /> : <Eye className="h-4 w-4" strokeWidth={1.8} />}
      </button>
    </div>
  );
};
