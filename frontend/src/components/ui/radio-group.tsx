"use client"

import * as React from "react"
import { RadioGroup as RadioGroupPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

function RadioGroup({
  className,
  ...props
}: React.ComponentProps<typeof RadioGroupPrimitive.Root>) {
  return (
    <RadioGroupPrimitive.Root
      data-slot="radio-group"
      className={cn("grid gap-2", className)}
      {...props}
    />
  )
}

function RadioGroupItem({
  className,
  children,
  ...props
}: React.ComponentProps<typeof RadioGroupPrimitive.Item>) {
  return (
    <RadioGroupPrimitive.Item
      data-slot="radio-group-item"
      className={cn(
        "group/radio relative inline-flex size-4 shrink-0 items-center justify-center rounded-full outline-none",
        "focus-visible:ring-3 focus-visible:ring-ring/50 data-[state=checked]:shadow-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children ?? (
        <span className="relative size-4 rounded-full border-[0.5px] border-border bg-input-surface shadow-[0_1px_2px_0_var(--tw-shadow-color)] shadow-foreground/10 group-data-[state=checked]/radio:shadow-none">
          <span className="absolute left-1/2 top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground opacity-0 group-data-[state=checked]/radio:opacity-100" />
        </span>
      )}
    </RadioGroupPrimitive.Item>
  )
}

type RadioFieldProps = {
  value: string
  label: string
  description?: string
  type?: "Default" | "Box"
  controlPlacement?: "Start" | "End"
  disabled?: boolean
  className?: string
}

function RadioField({
  value,
  label,
  description,
  type = "Default",
  controlPlacement = "Start",
  disabled,
  className,
}: RadioFieldProps) {
  const content = (
    <span className="flex min-w-0 flex-1 flex-col items-start justify-center gap-1.5 pt-px text-left">
      <span className="w-full text-sm font-medium leading-5 text-foreground">{label}</span>
      {description && (
        <span className="w-full text-sm font-normal leading-5 text-muted-foreground">
          {description}
        </span>
      )}
    </span>
  )

  return (
    <RadioGroupItem
      value={value}
      disabled={disabled}
      aria-label={label}
      className={cn(
        "h-auto w-full gap-3 overflow-visible rounded-none border-0 bg-transparent p-0 text-left shadow-none",
        "focus-visible:ring-0 focus-visible:shadow-[0_0_0_3px_var(--outline)]",
        type === "Box" &&
          "rounded-lg border border-border bg-input-surface p-3 data-[state=checked]:border-outline data-[state=checked]:bg-accent",
        controlPlacement === "End" && "justify-between",
        className,
      )}
    >
      {contentPlacement(controlPlacement, content)}
    </RadioGroupItem>
  )
}

function contentPlacement(placement: "Start" | "End", content: React.ReactNode) {
  return (
    <>
      {placement === "Start" && (
        <span className="relative size-4 shrink-0 rounded-full border-[0.5px] border-border bg-input-surface shadow-[0_1px_2px_0_var(--tw-shadow-color)] shadow-foreground/10 group-data-[state=checked]/radio:shadow-none">
          <span className="absolute left-1/2 top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground opacity-0 group-data-[state=checked]/radio:opacity-100" />
        </span>
      )}
      {content}
      {placement === "End" && (
        <span className="relative size-4 shrink-0 rounded-full border-[0.5px] border-border bg-input-surface shadow-[0_1px_2px_0_var(--tw-shadow-color)] shadow-foreground/10 group-data-[state=checked]/radio:shadow-none">
          <span className="absolute left-1/2 top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground opacity-0 group-data-[state=checked]/radio:opacity-100" />
        </span>
      )}
    </>
  )
}

type RadioControlProps = React.ComponentProps<typeof RadioGroupPrimitive.Item> & {
  state?: "Enabled" | "Disabled" | "Shimmer"
}

function RadioControl({ className, disabled, state = "Enabled", ...props }: RadioControlProps) {
  const isShimmer = state === "Shimmer"
  const isDisabled = disabled || state === "Disabled"
  return (
    <RadioGroupPrimitive.Item
      data-slot="radio-control"
      data-control-state={isShimmer ? "Shimmer" : isDisabled ? "Disabled" : "Enabled"}
      disabled={isDisabled || isShimmer}
      aria-busy={isShimmer || undefined}
      className={cn(
        "group/hr-radio relative inline-flex size-6 shrink-0 items-center justify-center rounded-full border-0 bg-transparent p-0 outline-none disabled:cursor-not-allowed",
        "before:pointer-events-none before:absolute before:inset-px before:rounded-full before:content-[''] focus-visible:before:shadow-[0_0_0_3px_var(--outline)]",
        className,
      )}
      {...props}
    >
      {isShimmer ? (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-[2px] rounded-full bg-gradient-to-r from-white/4 via-transparent via-[50.385%] to-white/4"
        />
      ) : (
        <span aria-hidden="true" className="pointer-events-none absolute inset-0">
          {/* Original 24px Figma SVGs supply the geometry; tokens supply each theme's color. */}
          <span className="absolute inset-0 bg-black [mask-image:url('/assets/hr-radio/radio-light-off.svg')] [mask-repeat:no-repeat] group-data-[state=checked]/hr-radio:hidden group-disabled/hr-radio:hidden dark:bg-white" />
          <span className="absolute inset-0 hidden bg-foreground [mask-image:url('/assets/hr-radio/radio-light-on.svg')] [mask-repeat:no-repeat] group-data-[state=checked]/hr-radio:block group-disabled/hr-radio:!hidden" />
          <span className="absolute inset-0 hidden bg-border [mask-image:url('/assets/hr-radio/radio-disabled-off.svg')] [mask-repeat:no-repeat] group-disabled/hr-radio:block group-data-[state=checked]/hr-radio:!hidden" />
          <span className="absolute inset-0 hidden bg-border [mask-image:url('/assets/hr-radio/radio-disabled-on.svg')] [mask-repeat:no-repeat] group-disabled/hr-radio:group-data-[state=checked]/hr-radio:block" />
        </span>
      )}
    </RadioGroupPrimitive.Item>
  )
}

type RadioHrFieldProps = Omit<RadioControlProps, "state"> & {
  state?: RadioControlProps["state"] | "Default" | "Focus"
  label?: string
  description?: string
  showText?: boolean
}

function RadioHrField({
  label,
  description,
  showText = false,
  state = "Default",
  className,
  ...props
}: RadioHrFieldProps) {
  const id = React.useId()
  const controlId = props.id ?? id
  const labelId = `${id}-label`
  const descriptionId = `${id}-description`
  return (
    <div
      data-slot="radio-hr-field"
      data-field-state={state}
      className={cn("flex items-start gap-3", className)}
    >
      <RadioControl
        state={state === "Default" || state === "Focus" ? "Enabled" : state}
        className={state === "Focus" ? "before:shadow-[0_0_0_3px_var(--outline)]" : undefined}
        id={controlId}
        aria-label={!showText ? label : undefined}
        aria-labelledby={showText ? labelId : undefined}
        aria-describedby={showText && description ? descriptionId : undefined}
        {...props}
      />
      {showText && (
        <div className="flex min-w-0 flex-col gap-1.5 pt-px">
          <label id={labelId} htmlFor={controlId} className="text-sm font-medium leading-none">
            {label}
          </label>
          {description && (
            <span
              id={descriptionId}
              className="text-sm font-normal leading-5 text-muted-foreground"
            >
              {description}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

export { RadioControl, RadioField, RadioHrField, RadioGroup, RadioGroupItem }
