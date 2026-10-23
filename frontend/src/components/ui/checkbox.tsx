"use client"

import * as React from "react"
import { Checkbox as CheckboxRoot, CheckboxIndicator } from "@radix-ui/react-checkbox"
import { Minus } from "lucide-react"

import { cn } from "@/lib/utils"

function Checkbox({ className, ...props }: React.ComponentProps<typeof CheckboxRoot>) {
  return (
    <CheckboxRoot
      data-slot="checkbox"
      className={cn(
        "peer group/checkbox size-4 shrink-0 rounded-xs border-[0.5px] border-input bg-input-surface shadow-xs outline-none transition-[color,box-shadow]",
        "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground",
        "data-[state=indeterminate]:border-primary data-[state=indeterminate]:bg-primary data-[state=indeterminate]:text-primary-foreground",
        className,
      )}
      {...props}
    >
      <CheckboxIndicator
        data-slot="checkbox-indicator"
        className="flex items-center justify-center text-current"
      >
        <img
          src="/assets/hr-checkbox/base-check.svg"
          alt=""
          width={14}
          height={14}
          className="group-data-[state=indeterminate]/checkbox:hidden"
        />
        <Minus className="hidden size-3.5 group-data-[state=indeterminate]/checkbox:block" />
      </CheckboxIndicator>
    </CheckboxRoot>
  )
}

export { Checkbox }
