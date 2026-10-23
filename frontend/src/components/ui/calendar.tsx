import * as React from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { format } from "date-fns"
import { DayPicker, useDayPicker, type MonthCaptionProps } from "react-day-picker"

import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"

export type CalendarProps = React.ComponentProps<typeof DayPicker>

function CalendarCaption({ calendarMonth }: MonthCaptionProps) {
  const { goToMonth, nextMonth, previousMonth } = useDayPicker()
  const navButton = cn(
    buttonVariants({ variant: "ghost", size: "icon-sm" }),
    "absolute text-muted-foreground hover:text-foreground disabled:pointer-events-none disabled:opacity-40",
  )
  return (
    <div className="relative flex h-9 items-center justify-center">
      <button
        type="button"
        aria-label="Go to previous month"
        disabled={!previousMonth}
        onClick={() => previousMonth && goToMonth(previousMonth)}
        className={cn(navButton, "left-1")}
      >
        <ChevronLeft className="size-4" />
      </button>
      <span className="text-sm font-medium text-foreground">
        {format(calendarMonth.date, "LLLL yyyy")}
      </span>
      <button
        type="button"
        aria-label="Go to next month"
        disabled={!nextMonth}
        onClick={() => nextMonth && goToMonth(nextMonth)}
        className={cn(navButton, "right-1")}
      >
        <ChevronRight className="size-4" />
      </button>
    </div>
  )
}

function Calendar({ className, classNames, showOutsideDays = true, ...props }: CalendarProps) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      hideNavigation
      className={cn("p-3", className)}
      classNames={{
        months: "flex flex-col gap-4",
        month: "flex flex-col gap-4",
        month_grid: "w-full border-collapse",
        weekdays: "flex",
        weekday: "w-9 text-center text-xs font-normal text-muted-foreground",
        week: "mt-1 flex w-full",
        day: "relative size-9 p-0 text-center text-sm first:rounded-l-md last:rounded-r-md focus-within:relative focus-within:z-20",
        day_button: cn(
          buttonVariants({ variant: "ghost", size: "icon-sm" }),
          "size-9 rounded-md p-0 font-normal",
        ),
        selected:
          "[&>button]:bg-primary [&>button]:text-primary-foreground [&>button]:hover:bg-primary",
        range_start:
          "rounded-l-md bg-accent [&>button]:bg-primary [&>button]:text-primary-foreground",
        range_end:
          "rounded-r-md bg-accent [&>button]:bg-primary [&>button]:text-primary-foreground",
        range_middle:
          "bg-accent [&>button]:bg-transparent [&>button]:text-foreground [&>button]:hover:bg-transparent",
        today: "[&>button]:border [&>button]:border-border",
        outside: "text-muted-foreground/40 [&>button]:text-muted-foreground/40",
        disabled: "text-muted-foreground/30",
        hidden: "invisible",
        ...classNames,
      }}
      components={{ MonthCaption: CalendarCaption }}
      {...props}
    />
  )
}

export { Calendar }
